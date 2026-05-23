"""
scripts/run_regression.py
─────────────────────────────────────────────────────
Offline regression harness for the backend pipeline.

Executes the full pipeline in-process against a set of
synthetic scenarios and writes a regression report to
output/regression/regression_report_{timestamp}.json.

Usage:
    python scripts/run_regression.py
    python scripts/run_regression.py --scenarios normal high_nulls drift
    python scripts/run_regression.py --rows 200 --no-agents

Does NOT start Kafka or Docker.  Runs preprocessing and
(optionally) agents against in-memory generated data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import yaml

# ─── Ensure project root is on sys.path ──────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv()


SCENARIOS = ["normal", "high_nulls", "many_outliers", "drift", "mixed"]

CHECKS: List[Dict[str, Any]] = [
    {"name": "health_score_present",    "path": "health_score",           "type": "exists"},
    {"name": "health_score_range",      "path": "health_score",           "type": "range",  "min": 0, "max": 100},
    {"name": "total_rows_positive",     "path": "total_rows",             "type": "gt",     "value": 0},
    {"name": "anomaly_count_int",       "path": "anomaly_count",          "type": "exists"},
    {"name": "volume_pillar_present",   "path": "volume",                 "type": "exists"},
    {"name": "freshness_pillar_present","path": "freshness",              "type": "exists"},
    {"name": "schema_pillar_present",   "path": "schema",                 "type": "exists"},
    {"name": "distribution_present",    "path": "distribution",           "type": "exists"},
    {"name": "lineage_present",         "path": "lineage",                "type": "exists"},
    {"name": "high_nulls_has_anomaly",  "path": "anomaly_count",          "type": "gt",     "value": 0,
     "only_scenarios": ["high_nulls", "mixed"]},
    {"name": "outlier_detected",        "path": "distribution.outlier_stats.glucose_level.outlier_count",
     "type": "gt", "value": 0, "only_scenarios": ["many_outliers", "mixed"]},
]


def _get_nested(data: Dict, path: str) -> Any:
    parts = path.split(".")
    cur: Any = data
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _run_check(check: Dict, scenario: str, metrics: Dict) -> Dict[str, Any]:
    only = check.get("only_scenarios")
    if only and scenario not in only:
        return {"name": check["name"], "status": "SKIPPED", "reason": f"not applicable to '{scenario}'"}

    value = _get_nested(metrics, check["path"])
    check_type = check["type"]

    if check_type == "exists":
        passed = value is not None
    elif check_type == "range":
        passed = value is not None and check["min"] <= float(value) <= check["max"]
    elif check_type == "gt":
        passed = value is not None and float(value) > check["value"]
    else:
        passed = False

    return {
        "name": check["name"],
        "status": "PASS" if passed else "FAIL",
        "value": value,
        "expected": check.get("value") or f"{check.get('min')}–{check.get('max')}",
    }


def _run_scenario(
    scenario: str,
    rows: int,
    run_agents: bool,
    config: Dict,
) -> Dict[str, Any]:
    from scripts.generate_synthetic_data import generate_dataset
    from backend.services.preprocessing_service import run_preprocessing
    from backend.services.pii_service import mask_metrics_json, mask_etl_log, save_sanitized_metrics

    run_id = f"REG_{scenario.upper()}_{uuid.uuid4().hex[:6].upper()}"
    output_dir = os.path.join("output", "regression", run_id)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  [scenario:{scenario}] run_id={run_id} rows={rows}")

    # Generate data
    t0 = time.time()
    records = generate_dataset(scenario=scenario, rows=rows)
    print(f"  [scenario:{scenario}] Generated {len(records)} records in {time.time()-t0:.2f}s")

    # Build streaming metadata stub
    streaming_metadata = {
        "events_received": len(records),
        "events_valid": len(records),
        "events_invalid": 0,
        "schema_errors": [],
        "consumer_lag_avg": 0,
        "consumer_lag_max": 0,
        "window_size": len(records),
        "api_timeouts": 0,
    }

    # Preprocessing
    t0 = time.time()
    metrics = run_preprocessing(
        event_buffer=records,
        streaming_metadata=streaming_metadata,
        run_id=run_id,
        config=config,
        output_dir=output_dir,
    )
    pp_duration = round(time.time() - t0, 2)
    print(f"  [scenario:{scenario}] Preprocessing done in {pp_duration}s — health={metrics['health_score']}")

    # PII masking
    try:
        masked_metrics = mask_metrics_json(metrics)
    except RuntimeError as exc:
        return {
            "run_id": run_id,
            "scenario": scenario,
            "rows": rows,
            "status": "FAILED",
            "error": f"PII masking failed: {exc}",
            "checks": [],
            "preprocessing_duration_s": pp_duration,
        }

    save_sanitized_metrics(masked_metrics, output_dir)

    log_path = os.path.join(output_dir, "etl_run.log")
    if os.path.exists(log_path):
        mask_etl_log(log_path, output_dir)

    # Checks
    check_results = [_run_check(c, scenario, masked_metrics) for c in CHECKS]
    passed = sum(1 for r in check_results if r["status"] == "PASS")
    failed = sum(1 for r in check_results if r["status"] == "FAIL")
    skipped = sum(1 for r in check_results if r["status"] == "SKIPPED")

    # Agents (optional)
    agent_results: Dict = {}
    if run_agents:
        try:
            from backend.agents.graph import run_agent_pipeline

            log_text = ""
            slog = os.path.join(output_dir, "sanitized_log.txt")
            if os.path.exists(slog):
                with open(slog) as fh:
                    log_text = fh.read()

            t0 = time.time()
            agent_state = run_agent_pipeline(
                run_id=run_id,
                sanitized_metrics=masked_metrics,
                sanitized_log_text=log_text,
                streaming_metadata=streaming_metadata,
                output_dir=output_dir,
            )
            agent_duration = round(time.time() - t0, 2)

            conf_path = os.path.join(output_dir, "agent_confidence.json")
            conf_data: Dict = {}
            if os.path.exists(conf_path):
                with open(conf_path) as fc:
                    conf_data = json.load(fc)

            agent_results = {
                "status": "COMPLETED" if not agent_state.get("error") else "FAILED",
                "error": agent_state.get("error"),
                "confidence_scores": conf_data,
                "duration_s": agent_duration,
            }
            print(f"  [scenario:{scenario}] Agents done in {agent_duration}s | error={agent_state.get('error')}")
        except Exception as exc:
            agent_results = {"status": "FAILED", "error": str(exc)}
            print(f"  [scenario:{scenario}] Agent run failed: {exc}")

    overall = "PASS" if failed == 0 else "FAIL"
    print(f"  [scenario:{scenario}] Checks: {passed} PASS / {failed} FAIL / {skipped} SKIPPED → {overall}")

    return {
        "run_id": run_id,
        "scenario": scenario,
        "rows": rows,
        "status": overall,
        "health_score": metrics.get("health_score"),
        "health_label": metrics.get("health_label"),
        "anomaly_count": metrics.get("anomaly_count"),
        "preprocessing_duration_s": pp_duration,
        "checks": check_results,
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_skipped": skipped,
        "agents": agent_results,
        "output_dir": output_dir,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend regression harness")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=SCENARIOS,
        default=SCENARIOS,
        help="Scenarios to run (default: all)",
    )
    parser.add_argument("--rows", type=int, default=300, help="Rows per scenario")
    parser.add_argument(
        "--no-agents",
        action="store_true",
        help="Skip LangGraph agent calls (faster, no LLM cost)",
    )
    args = parser.parse_args()

    # Load config
    cfg: Dict = {}
    if os.path.exists("config.yaml"):
        with open("config.yaml") as fh:
            cfg = yaml.safe_load(fh) or {}

    run_agents = not args.no_agents

    print("=" * 60)
    print(f"Clinical Trial AI Observability — Regression Harness")
    print(f"Scenarios: {args.scenarios}")
    print(f"Rows per scenario: {args.rows}")
    print(f"Run agents: {run_agents}")
    print("=" * 60)

    os.makedirs(os.path.join("output", "regression"), exist_ok=True)

    results: List[Dict] = []
    total_start = time.time()

    for scenario in args.scenarios:
        result = _run_scenario(
            scenario=scenario,
            rows=args.rows,
            run_agents=run_agents,
            config=cfg,
        )
        results.append(result)

    total_duration = round(time.time() - total_start, 2)

    # Build report
    total_checks = sum(r["checks_passed"] + r["checks_failed"] for r in results)
    total_passed = sum(r["checks_passed"] for r in results)
    total_failed = sum(r["checks_failed"] for r in results)
    all_pass = total_failed == 0

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scenarios_run": args.scenarios,
        "rows_per_scenario": args.rows,
        "agents_enabled": run_agents,
        "total_duration_s": total_duration,
        "overall_status": "PASS" if all_pass else "FAIL",
        "total_checks": total_checks,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "scenario_results": results,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join("output", "regression", f"regression_report_{ts}.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("\n" + "=" * 60)
    print(f"REGRESSION SUMMARY")
    print(f"  Overall:   {'✓ PASS' if all_pass else '✗ FAIL'}")
    print(f"  Scenarios: {len(results)}")
    print(f"  Checks:    {total_passed} PASS / {total_failed} FAIL")
    print(f"  Duration:  {total_duration}s")
    print(f"  Report:    {report_path}")
    print("=" * 60)

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
