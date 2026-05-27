from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/seg-dashboard", tags=["Segregated Dashboard"])

logger = logging.getLogger(__name__)

_STANDARD_COLUMNS = [
    "patient_id",
    "patient_name",
    "age",
    "medication",
    "blood_pressure",
    "glucose_level",
    "side_effect",
    "severity",
    "visit_date",
    "hospital_name",
]
_STANDARD_COLUMNS_EXTENDED = _STANDARD_COLUMNS + ["gender", "diagnosis", "treatment_group", "side_effects"]
_AGENT_ORDER = ["data_quality", "log_analysis", "rca", "recommendation", "compliance"]
_NOT_FOUND_DETAIL = "Run not found or not approved"


def _load_config() -> dict[str, Any]:
    try:
        with open("config.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Could not load config.yaml", exc_info=True)
        return {}


def _get_runs_dir_and_expected_records() -> tuple[str, int]:
    cfg = _load_config()
    output_cfg = cfg.get("output", {})
    runs_dir = output_cfg.get("runs_directory", os.path.join("output", "runs"))
    expected = cfg.get("data", {}).get("expected_row_count", 0)
    try:
        expected_int = int(expected)
    except (TypeError, ValueError):
        expected_int = 0
    return runs_dir, expected_int


def _load_run_json(run_id: str, filename: str, runs_dir: str) -> Optional[dict | list]:
    path = os.path.join(runs_dir, run_id, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.warning("Failed to parse JSON: %s", path, exc_info=True)
        return None


def _to_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _approved_audit_or_404(run_id: str, runs_dir: str) -> dict[str, Any]:
    if not os.path.isdir(os.path.join(runs_dir, run_id)):
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    audit = _load_run_json(run_id, "audit_trail.json", runs_dir)
    if not isinstance(audit, dict) or audit.get("pipeline_status") != "approved":
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    return audit


def _run_metadata(run_id: str, runs_dir: str, records_expected: int, audit: dict[str, Any]) -> dict[str, Any]:
    started_at = audit.get("pipeline_started_at")
    completed_at = audit.get("pipeline_completed_at")
    started_dt = _to_dt(started_at)
    completed_dt = _to_dt(completed_at)
    duration_seconds = 0
    if started_dt and completed_dt:
        duration_seconds = max(0, int((completed_dt - started_dt).total_seconds()))

    fingerprint = _load_run_json(run_id, "data_fingerprint.json", runs_dir)
    records_processed = 0
    if isinstance(fingerprint, dict):
        try:
            records_processed = int(fingerprint.get("row_count", 0) or 0)
        except (TypeError, ValueError):
            records_processed = 0

    hitl = audit.get("hitl_decision") or {}
    if not isinstance(hitl, dict):
        hitl = {}

    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration_seconds,
        "records_processed": records_processed,
        "records_expected": records_expected,
        "status": "approved",
        "model": "gpt-4o",
        "approved_at": hitl.get("decided_at"),
        "approved_by": hitl.get("reviewer_id"),
    }


def _parse_findings(raw_response: str, confidence: int) -> list[dict[str, Any]]:
    if not isinstance(raw_response, str) or not raw_response.strip():
        return []

    headers = [
        "PILLAR",
        "STATUS",
        "FINDING",
        "PRIORITY",
        "RESPONSIBLE TEAM",
        "ACTION",
        "RATIONALE",
        "EVIDENCE",
        "INCIDENT",
        "ROOT CAUSE",
        "RECOMMENDATION",
        "COMPLIANCE STATUS",
    ]
    header_set = set(headers)

    blocks: list[dict[str, str]] = []
    lines = raw_response.splitlines()

    # Prefer incident-style parser when response is incident formatted.
    if any(line.strip().upper().startswith("INCIDENT:") for line in lines):
        current: dict[str, str] = {}
        for line in lines:
            txt = line.strip()
            if not txt:
                continue

            if txt.upper().startswith("INCIDENT:"):
                if current:
                    blocks.append(current)
                    current = {}
                incident_val = txt[len("INCIDENT:") :].strip()
                priority_val = None
                if " | PRIORITY:" in incident_val.upper():
                    parts = incident_val.split("|", 1)
                    incident_val = parts[0].strip()
                    pr_part = parts[1].strip()
                    if ":" in pr_part:
                        _, pr_val = pr_part.split(":", 1)
                        priority_val = pr_val.strip()
                current["INCIDENT"] = incident_val
                if priority_val:
                    current["PRIORITY"] = priority_val
                continue

            matched = False
            for header in ["STATUS", "FINDING", "ACTION", "ROOT CAUSE", "RATIONALE", "RECOMMENDATION", "EVIDENCE"]:
                prefix = f"{header}:"
                if txt.upper().startswith(prefix):
                    current[header] = txt[len(prefix) :].strip()
                    matched = True
                    break
            if not matched and current:
                last_key = next(reversed(current))
                current[last_key] = (current[last_key] + " " + txt).strip()
        if current:
            blocks.append(current)
    # Parse operational status / log-analysis style outputs.
    elif any(
        line.strip().upper().startswith(prefix)
        for line in lines
        for prefix in ["ERROR COUNT:", "WARNING COUNT:", "OPERATIONAL STATUS:", "SUMMARY:"]
    ):
        current = {}
        for line in lines:
            txt = line.strip()
            if not txt or ":" not in txt:
                continue
            key, value = txt.split(":", 1)
            key_u = key.strip().upper()
            value_s = value.strip()
            if key_u:
                current[key_u] = value_s
        if current:
            op_status = (current.get("OPERATIONAL STATUS") or "").upper()
            warning_count = current.get("WARNING COUNT", "0")
            error_count = current.get("ERROR COUNT", "0")
            try:
                error_n = int(str(error_count).strip())
            except (TypeError, ValueError):
                error_n = 0
            try:
                warn_n = int(str(warning_count).strip())
            except (TypeError, ValueError):
                warn_n = 0

            if error_n > 0:
                current["STATUS"] = "ANOMALY"
            elif warn_n > 0:
                current["STATUS"] = "WARNING"
            elif op_status in {"HEALTHY", "OK"}:
                current["STATUS"] = "OK"
            else:
                current["STATUS"] = "WARNING"

            if "FINDING" not in current:
                current["FINDING"] = current.get("SUMMARY", "Operational checks completed.")
            if "RATIONALE" not in current:
                current["RATIONALE"] = "Review warnings/errors and confirm log pipeline stability."
            if "PILLAR" not in current:
                current["PILLAR"] = "Log Analysis"
            blocks.append(current)
    else:
        current = {}
        for line in lines:
            txt = line.strip()
            if not txt:
                continue
            matched = False
            for header in headers:
                prefix = f"{header}:"
                if txt.upper().startswith(prefix):
                    value = txt[len(prefix) :].strip()
                    if header in ("PILLAR", "INCIDENT") and current:
                        blocks.append(current)
                        current = {}
                    current[header] = value
                    matched = True
                    break
            if not matched and current:
                last_key = next(reversed(current))
                current[last_key] = (current[last_key] + " " + txt).strip()
        if current:
            blocks.append(current)

    findings: list[dict[str, Any]] = []
    for block in blocks:
        if not any(k in block for k in ("PILLAR", "INCIDENT", "STATUS", "COMPLIANCE STATUS", "FINDING", "ACTION", "ROOT CAUSE")):
            continue
        status = (block.get("STATUS") or "").upper().strip()
        priority = (block.get("PRIORITY") or "").upper().strip()
        severity_map = {
            "ANOMALY": "critical",
            "WARNING": "high",
            "OK": "low",
            "NEEDS REVISION": "critical",
            "FAIL": "critical",
            "WARN": "high",
            "PASS": "low",
        }
        severity = severity_map.get(status, "medium")
        if status == "" and priority in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            severity = priority.lower()

        finding_type = None
        for key in ["PILLAR", "INCIDENT", "COMPLIANCE STATUS", "STATUS"]:
            if key in block and block[key]:
                finding_type = f"{key}: {block[key]}"
                break
        if not finding_type:
            first_key = next(iter(block.keys()), "FINDING")
            finding_type = f"{first_key}: {block.get(first_key, '')}".strip()

        description = (
            block.get("FINDING")
            or block.get("ACTION")
            or block.get("ROOT CAUSE")
            or "No finding details provided."
        )
        desc_lower = description.lower()
        desc_norm = desc_lower.replace(" ", "_")
        affected_field = next(
            (
                col
                for col in _STANDARD_COLUMNS_EXTENDED
                if col in desc_lower or col in desc_norm or col.replace("_", " ") in desc_lower
            ),
            None,
        )

        recommendation = (
            block.get("RATIONALE")
            or block.get("RECOMMENDATION")
            or "Review and investigate the flagged issue."
        )

        findings.append(
            {
                "finding_type": finding_type,
                "severity": severity,
                "confidence": confidence,
                "description": description,
                "affected_field": affected_field,
                "recommendation": recommendation,
            }
        )

    return findings


@router.get("/approved-runs")
def list_approved_runs() -> list[dict[str, Any]]:
    runs_dir, records_expected = _get_runs_dir_and_expected_records()
    if not os.path.isdir(runs_dir):
        return []

    items: list[dict[str, Any]] = []
    for run_id in os.listdir(runs_dir):
        run_path = os.path.join(runs_dir, run_id)
        if not os.path.isdir(run_path):
            continue
        audit = _load_run_json(run_id, "audit_trail.json", runs_dir)
        if not isinstance(audit, dict):
            continue
        if audit.get("pipeline_status") != "approved":
            continue
        items.append(_run_metadata(run_id, runs_dir, records_expected, audit))

    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return items


@router.get("/run/{run_id}/info")
def run_info(run_id: str) -> dict[str, Any]:
    runs_dir, records_expected = _get_runs_dir_and_expected_records()
    audit = _approved_audit_or_404(run_id, runs_dir)
    return _run_metadata(run_id, runs_dir, records_expected, audit)


@router.get("/run/{run_id}/kpis")
def run_kpis(run_id: str) -> dict[str, Any]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    rolling = _load_run_json(run_id, "rolling_metrics.json", runs_dir)
    if not isinstance(rolling, dict):
        rolling = {}

    overall_health_score = rolling.get("overall_health_score")
    if not isinstance(overall_health_score, (int, float)):
        overall_health_score = rolling.get("health_score")
    try:
        compliance_score = min(100, int(float(overall_health_score) * 0.95))
    except (TypeError, ValueError):
        compliance_score = 0

    pillar_volume = rolling.get("pillar_volume") or rolling.get("volume") or {}
    if not isinstance(pillar_volume, dict):
        pillar_volume = {}

    records_processed_value = pillar_volume.get("row_count", pillar_volume.get("total_rows", 0))
    if not records_processed_value:
        fingerprint = _load_run_json(run_id, "data_fingerprint.json", runs_dir)
        if isinstance(fingerprint, dict):
            records_processed_value = fingerprint.get("row_count", 0)
    return {
        "anomalies_detected": int(rolling.get("anomaly_count", 0) or 0),
        "records_processed": int(records_processed_value or 0),
        "compliance_score": compliance_score,
    }


@router.get("/run/{run_id}/null-rate")
def null_rate(run_id: str) -> list[dict[str, Any]]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    rolling = _load_run_json(run_id, "rolling_metrics.json", runs_dir)
    if not isinstance(rolling, dict):
        return []

    pillar_schema = rolling.get("pillar_schema") or rolling.get("schema") or {}
    if not isinstance(pillar_schema, dict):
        return []
    null_report = pillar_schema.get("null_report") or pillar_schema.get("null_stats") or {}
    if not isinstance(null_report, dict):
        return []

    results: list[dict[str, Any]] = []
    for col in _STANDARD_COLUMNS:
        entry = null_report.get(col)
        if not isinstance(entry, dict):
            continue
        try:
            pct = float(entry.get("null_pct", 0.0) or 0.0)
        except (TypeError, ValueError):
            pct = 0.0
        results.append({"column": col, "null_pct": pct, "threshold": 5})

    # Compatibility fallback: some runs have a different schema set (e.g. gender/diagnosis),
    # so return available columns when strict schema filtering yields no rows.
    if not results:
        for col, entry in null_report.items():
            if not isinstance(col, str) or not isinstance(entry, dict):
                continue
            try:
                pct = float(entry.get("null_pct", 0.0) or 0.0)
            except (TypeError, ValueError):
                pct = 0.0
            results.append({"column": col, "null_pct": pct, "threshold": 5})

    results.sort(key=lambda x: x["null_pct"], reverse=True)
    return results


@router.get("/run/{run_id}/severity-distribution")
def severity_distribution(run_id: str) -> list[dict[str, Any]]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    rolling = _load_run_json(run_id, "rolling_metrics.json", runs_dir)
    if not isinstance(rolling, dict):
        rolling = {}

    pillar_distribution = rolling.get("pillar_distribution") or rolling.get("distribution") or {}
    if not isinstance(pillar_distribution, dict):
        pillar_distribution = {}
    raw_dist = pillar_distribution.get("severity_distribution") or {}
    if not isinstance(raw_dist, dict):
        raw_dist = {}

    anomaly_count = int(rolling.get("anomaly_count", 0) or 0)
    ordered = ["Critical", "High", "Medium", "Low"]
    colors = {
        "Critical": "#EF4444",
        "High": "#F59E0B",
        "Medium": "#3B82F6",
        "Low": "#10B981",
    }

    counts: dict[str, int] = {}
    for sev in ordered:
        proportion = raw_dist.get(sev, 0.0)
        try:
            proportion_val = float(proportion)
            if proportion_val > 1.0:
                # Backward compatibility: some runs persist percentages like 50/28/16/6.
                proportion_val = proportion_val / 100.0
            counts[sev] = int(round(proportion_val * anomaly_count))
        except (TypeError, ValueError):
            counts[sev] = 0

    total_counts = sum(counts.values())
    response: list[dict[str, Any]] = []
    for sev in ordered:
        count = counts[sev]
        pct = round((count / total_counts) * 100, 1) if total_counts > 0 else 0.0
        response.append({"severity": sev, "count": count, "pct": pct, "color": colors[sev]})
    return response


@router.get("/run/{run_id}/agent-confidence")
def agent_confidence(run_id: str) -> list[dict[str, Any]]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    confidence_data = _load_run_json(run_id, "agent_confidence.json", runs_dir)
    by_agent: dict[str, Any] = {}
    if isinstance(confidence_data, list):
        for entry in confidence_data:
            if isinstance(entry, dict) and entry.get("agent"):
                by_agent[str(entry["agent"])] = entry.get("score")
    elif isinstance(confidence_data, dict):
        for key, value in confidence_data.items():
            if not isinstance(key, str):
                continue
            normalized = key.removesuffix("_agent")
            by_agent[normalized] = value
            by_agent[key] = value
    else:
        return []

    result: list[dict[str, Any]] = []
    for agent in _AGENT_ORDER:
        score = by_agent.get(agent)
        if score is None:
            score = by_agent.get(f"{agent}_agent")
        if score is None:
            continue
        status = "Failed"
        if isinstance(score, (int, float)) and score >= 0:
            status = "Completed"
        confidence_val = int(score) if isinstance(score, (int, float)) else score
        result.append({"agent": agent, "confidence": confidence_val, "status": status})
    return result


@router.get("/run/{run_id}/anomaly-summary")
def anomaly_summary(run_id: str) -> list[dict[str, Any]]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    rolling = _load_run_json(run_id, "rolling_metrics.json", runs_dir)
    if not isinstance(rolling, dict):
        return []

    anomalies = rolling.get("anomalies_detected", rolling.get("anomalies"))
    if not isinstance(anomalies, list):
        return []

    buckets: dict[str, list[str]] = {"Critical": [], "High": [], "Medium": [], "Low": []}
    for item in anomalies:
        if not isinstance(item, str):
            continue
        label = item.strip()
        low = label.lower()
        if any(key in low for key in ["phi", "masking", "etl_errors"]):
            buckets["Critical"].append(label)
        elif any(key in low for key in ["missing_columns", "duplicate", "schema", "outliers"]):
            buckets["High"].append(label)
        elif any(key in low for key in ["drift", "null", "volume"]):
            buckets["Medium"].append(label)
        else:
            buckets["Low"].append(label)

    ordered = ["Critical", "High", "Medium", "Low"]
    out: list[dict[str, Any]] = []
    for sev in ordered:
        if not buckets[sev]:
            continue
        out.append(
            {
                "severity": sev,
                "count": len(buckets[sev]),
                "description": ", ".join(buckets[sev]),
            }
        )
    return out


@router.get("/run/{run_id}/token-usage")
def token_usage(run_id: str) -> dict[str, Any]:
    runs_dir, _ = _get_runs_dir_and_expected_records()
    _approved_audit_or_404(run_id, runs_dir)
    usage = _load_run_json(run_id, "token_usage.json", runs_dir)
    if not isinstance(usage, list):
        return {
            "run_total_input": 0,
            "run_total_output": 0,
            "run_total": 0,
            "estimated_cost": 0.0,
            "model": "gpt-4o",
            "by_agent": [],
        }

    run_total_input = 0
    run_total_output = 0
    run_total = 0
    estimated_cost = 0.0
    by_agent: list[dict[str, Any]] = []

    for row in usage:
        if not isinstance(row, dict):
            continue
        in_tok = int(row.get("input_tokens", 0) or 0)
        out_tok = int(row.get("output_tokens", 0) or 0)
        total_tok = int(row.get("total_tokens", 0) or 0)
        cost = float(row.get("estimated_cost_usd", 0.0) or 0.0)

        run_total_input += in_tok
        run_total_output += out_tok
        run_total += total_tok
        estimated_cost += cost

        raw_agent = row.get("agent") or row.get("agent_name")
        agent_name = raw_agent.removesuffix("_agent") if isinstance(raw_agent, str) else raw_agent
        by_agent.append({"agent": agent_name, "tokens": total_tok})

    for item in by_agent:
        item["pct"] = round((item["tokens"] / run_total) * 100, 1) if run_total > 0 else 0.0

    return {
        "run_total_input": run_total_input,
        "run_total_output": run_total_output,
        "run_total": run_total,
        "estimated_cost": round(estimated_cost, 4),
        "model": "gpt-4o",
        "by_agent": by_agent,
    }


@router.get("/run/{run_id}/findings/{agent}")
def agent_findings(run_id: str, agent: str) -> list[dict[str, Any]]:
    if agent not in _AGENT_ORDER:
        raise HTTPException(status_code=400, detail="Invalid agent")

    runs_dir, _ = _get_runs_dir_and_expected_records()
    audit = _approved_audit_or_404(run_id, runs_dir)

    entries = audit.get("entries")
    if not isinstance(entries, list):
        return []

    target_response = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("event_type") == "agent_response" and entry.get("agent") == agent:
            data = entry.get("data") or {}
            if isinstance(data, dict):
                target_response = data.get("response")
            break

    if not target_response:
        response_payload = _load_run_json(run_id, f"responses/{agent}_agent.json", runs_dir)
        if isinstance(response_payload, dict):
            target_response = response_payload.get("response")
    if not target_response:
        return []

    confidence_data = _load_run_json(run_id, "agent_confidence.json", runs_dir)
    confidence = 75
    if isinstance(confidence_data, list):
        for row in confidence_data:
            if isinstance(row, dict) and row.get("agent") == agent:
                try:
                    confidence = int(row.get("score", 75))
                except (TypeError, ValueError):
                    confidence = 75
                break
    elif isinstance(confidence_data, dict):
        raw_score = confidence_data.get(agent) or confidence_data.get(f"{agent}_agent")
        try:
            confidence = int(raw_score) if raw_score is not None else 75
        except (TypeError, ValueError):
            confidence = 75

    return _parse_findings(str(target_response), confidence)
