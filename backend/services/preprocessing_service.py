"""
backend/services/preprocessing_service.py
─────────────────────────────────────────────────────
Rolling Metrics Engine.
Input: event buffer (list of dicts) from Kafka window.
Computes all 5 observability pillars + health score.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


# ─── ETL Logger factory ──────────────────────────────────────────────────────

def _create_etl_logger(run_id: str, log_path: str) -> logging.Logger:
    logger = logging.getLogger(f"etl_{run_id}")
    logger.setLevel(logging.DEBUG)
    # Remove any inherited handlers
    logger.handlers.clear()
    logger.propagate = False

    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def _close_logger(logger: logging.Logger) -> None:
    """Flush and close ALL handlers.  Must be called before warning count."""
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


class _NumpyJSONEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy scalar/array types to native Python."""

    def default(self, o: Any) -> Any:  # type: ignore[override]
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            f = float(o)
            if np.isnan(o) or np.isinf(o):
                return None
            return f
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (pd.Timestamp, datetime)):
            return o.isoformat()
        return super().default(o)


def _count_log_levels(log_path: str) -> Dict[str, int]:
    """
    Count WARNING and ERROR lines in the ETL log.
    Splits each line by '|', takes parts[1].strip(),
    checks equality to exactly 'WARNING' or 'ERROR'.
    Never uses string.contains() to prevent false positives.
    """
    counts: Dict[str, int] = {"WARNING": 0, "ERROR": 0, "INFO": 0, "DEBUG": 0}
    if not os.path.exists(log_path):
        return counts
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split("|")
            if len(parts) >= 2:
                level = parts[1].strip()
                if level == "WARNING":
                    counts["WARNING"] += 1
                elif level == "ERROR":
                    counts["ERROR"] += 1
                elif level == "INFO":
                    counts["INFO"] += 1
                elif level == "DEBUG":
                    counts["DEBUG"] += 1
    return counts


# ─── Main function ───────────────────────────────────────────────────────────

def run_preprocessing(
    event_buffer: List[Dict[str, Any]],
    streaming_metadata: Dict[str, Any],
    run_id: str,
    config: Dict[str, Any],
    output_dir: str,
) -> Dict[str, Any]:
    """
    Convert Kafka event buffer → DataFrame → 5-pillar metrics.
    Writes rolling_metrics.json and etl_run.log.
    Returns the metrics dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "etl_run.log")
    logger = _create_etl_logger(run_id, log_path)

    cfg_pp = config.get("preprocessing", {})
    null_threshold = float(cfg_pp.get("null_threshold_pct", 5.0))
    iqr_mult = float(cfg_pp.get("outlier_iqr_multiplier", 1.5))
    ks_pvalue = float(cfg_pp.get("drift_ks_pvalue_threshold", 0.05))
    numeric_cols: List[str] = cfg_pp.get("numeric_columns", ["age", "glucose_level"])

    logger.info("=" * 60)
    logger.info(f"ETL Pipeline started | run_id={run_id}")
    logger.info("=" * 60)

    # ── 1. Streaming metadata ────────────────────────────────────────────────
    logger.info(f"Streaming metadata: {json.dumps(streaming_metadata)}")

    # ── 2. Convert buffer to DataFrame ───────────────────────────────────────
    if not event_buffer:
        logger.warning("Event buffer is empty — returning minimal metrics")
        _close_logger(logger)
        return _minimal_metrics(run_id, output_dir)

    df = pd.DataFrame(event_buffer)
    logger.info(f"DataFrame shape: {df.shape[0]} rows × {df.shape[1]} cols")

    # Coerce types
    for col in ["age", "glucose_level"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    total_rows = len(df)

    # ── 3. PILLAR 1: Volume ───────────────────────────────────────────────────
    expected_rows = config.get("data", {}).get("expected_row_count", 500)
    volume_ok = bool(total_rows >= expected_rows * 0.8)
    logger.info(f"PILLAR:VOLUME | rows={total_rows}, expected={expected_rows}, ok={volume_ok}")

    # ── 4. PILLAR 2: Freshness ────────────────────────────────────────────────
    freshness_max_days = config.get("data", {}).get("freshness_max_days", 7)
    event_arrival_latencies: List[float] = []

    if "event_timestamp" in df.columns:
        ts = pd.to_datetime(df["event_timestamp"], utc=True, errors="coerce")
        now_utc = pd.Timestamp.now(tz="UTC")
        latencies_ms = ((now_utc - ts).dt.total_seconds() * 1000).dropna().tolist()
        event_arrival_latencies = [round(v, 2) for v in latencies_ms]
        avg_latency = round(float(np.mean(latencies_ms)), 2) if latencies_ms else 0.0
        freshness_ok = bool(avg_latency < freshness_max_days * 24 * 3600 * 1000)
    else:
        avg_latency = 0.0
        freshness_ok = True

    days_since = 0
    if "visit_date" in df.columns:
        vd = pd.to_datetime(df["visit_date"], errors="coerce")
        if not vd.dropna().empty:
            most_recent_visit = vd.max()
            days_since = int((pd.Timestamp.now() - most_recent_visit).days)
            freshness_ok = bool(freshness_ok and (days_since <= freshness_max_days))

    logger.info(f"PILLAR:FRESHNESS | avg_latency_ms={avg_latency}, days_since_last_visit={days_since}, ok={freshness_ok}")

    # ── 5. PILLAR 3: Schema / Null Detection ─────────────────────────────────
    required_cols = config.get("validation", {}).get("expected_columns", [
        "patient_id", "patient_name", "age", "gender", "diagnosis",
        "treatment_group", "visit_date", "glucose_level", "side_effects", "severity",
    ])

    null_stats: Dict[str, Dict] = {}
    schema_issues: List[str] = []

    for col in required_cols:
        if col not in df.columns:
            schema_issues.append(f"Missing column: {col}")
            logger.warning(f"SCHEMA | Missing column: {col}")
            null_stats[col] = {"null_count": total_rows, "null_pct": 100.0, "exceeds_threshold": True}
            continue
        null_count = int(df[col].isna().sum())
        null_pct = round(null_count / total_rows * 100, 2) if total_rows > 0 else 0.0
        exceeds = bool(null_pct > null_threshold)
        null_stats[col] = {"null_count": null_count, "null_pct": null_pct, "exceeds_threshold": exceeds}
        if exceeds:
            logger.warning(f"SCHEMA | High null rate: {col}={null_pct:.1f}% (threshold={null_threshold}%)")
        else:
            logger.info(f"SCHEMA | {col}: null_pct={null_pct:.1f}%")

    # Duplicates
    if "patient_id" in df.columns:
        dup_count = int(df["patient_id"].duplicated().sum())
        dup_pct = round(dup_count / total_rows * 100, 2) if total_rows > 0 else 0.0
    else:
        dup_count = 0
        dup_pct = 0.0

    logger.info(f"SCHEMA | Duplicates: count={dup_count}, pct={dup_pct:.1f}%")

    # ── 6. PILLAR 4: Distribution / Outlier Detection ────────────────────────
    outlier_stats: Dict[str, Dict] = {}
    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if len(series) < 4:
            outlier_stats[col] = {"outlier_count": 0, "outlier_pct": 0.0, "q1": None, "q3": None, "iqr": None}
            continue
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - iqr_mult * iqr
        upper = q3 + iqr_mult * iqr
        outliers = series[(series < lower) | (series > upper)]
        out_count = int(len(outliers))
        out_pct = round(out_count / len(series) * 100, 2)
        outlier_stats[col] = {
            "outlier_count": out_count,
            "outlier_pct": out_pct,
            "q1": round(q1, 2),
            "median": round(float(series.median()), 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_fence": round(lower, 2),
            "upper_fence": round(upper, 2),
            "mean": round(float(series.mean()), 2),
            "std": round(float(series.std()), 2),
        }
        if out_count > 0:
            logger.warning(f"DISTRIBUTION | Outliers in {col}: count={out_count}, pct={out_pct:.1f}%")
        else:
            logger.info(f"DISTRIBUTION | {col}: no outliers detected")

    # Severity distribution
    severity_dist: Dict[str, int] = {}
    if "severity" in df.columns:
        severity_dist = {str(k): int(v) for k, v in df["severity"].value_counts().to_dict().items()}
        logger.info(f"DISTRIBUTION | Severity: {severity_dist}")

    # Side effects
    side_effect_dist: Dict[str, int] = {}
    if "side_effects" in df.columns:
        side_effect_dist = {str(k): int(v) for k, v in df["side_effects"].value_counts().head(10).to_dict().items()}

    # ── 7. PILLAR 5: Lineage / Drift Detection (KS-test) ─────────────────────
    baseline_path = config.get("data", {}).get("baseline_metrics_path", "config/baseline_metrics.json")
    drift_results: Dict[str, Dict] = {}

    if os.path.exists(baseline_path):
        try:
            with open(baseline_path, encoding="utf-8") as fh:
                baseline = json.load(fh)
            for col in numeric_cols:
                if col not in df.columns:
                    continue
                baseline_vals = baseline.get("distributions", {}).get(col, [])
                if len(baseline_vals) < 10:
                    continue
                current_vals = df[col].dropna().tolist()
                if len(current_vals) < 10:
                    continue
                ks_stat, p_value = stats.ks_2samp(baseline_vals, current_vals)
                drift_detected = bool(p_value < ks_pvalue)
                drift_results[col] = {
                    "ks_statistic": round(float(ks_stat), 4),
                    "p_value": round(float(p_value), 4),
                    "drift_detected": drift_detected,
                }
                if drift_detected:
                    logger.warning(f"LINEAGE | Drift detected in {col}: ks={ks_stat:.4f}, p={p_value:.4f}")
                else:
                    logger.info(f"LINEAGE | No drift in {col}: p={p_value:.4f}")
        except Exception as exc:
            logger.warning(f"LINEAGE | Baseline load failed: {exc}")
    else:
        logger.info("LINEAGE | No baseline file found — skipping drift detection")

    # Data sources present in buffer
    data_sources: List[str] = []
    if "source" in df.columns:
        data_sources = df["source"].dropna().unique().tolist()

    # ── 8. Compute health score ───────────────────────────────────────────────
    _close_logger(logger)
    log_counts = _count_log_levels(log_path)
    total_warnings = log_counts["WARNING"]
    total_errors = log_counts["ERROR"]

    anomalies: List[str] = []

    if not volume_ok:
        anomalies.append(f"Volume below threshold: {total_rows}/{expected_rows}")
    if not freshness_ok:
        anomalies.append(f"Data freshness issue: {days_since} days since last visit")
    for col, ns in null_stats.items():
        if ns.get("exceeds_threshold"):
            anomalies.append(f"High null rate in {col}: {ns['null_pct']:.1f}%")
    for col, od in outlier_stats.items():
        if od.get("outlier_pct", 0) > 10:
            anomalies.append(f"High outlier rate in {col}: {od['outlier_pct']:.1f}%")
    for col, dr in drift_results.items():
        if dr.get("drift_detected"):
            anomalies.append(f"Distribution drift in {col}: p={dr['p_value']:.4f}")
    if schema_issues:
        anomalies.extend(schema_issues)

    # Health score: start at 100, deduct per anomaly
    deductions = len(anomalies) * 5 + total_errors * 3 + total_warnings * 1
    health_score = max(0.0, 100.0 - deductions)
    health_label = (
        "Excellent" if health_score >= 90
        else "Good" if health_score >= 75
        else "Fair" if health_score >= 60
        else "Poor"
    )

    # ── 9. Assemble metrics dict ──────────────────────────────────────────────
    metrics: Dict[str, Any] = {
        "run_id": run_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": total_rows,
        "health_score": round(health_score, 1),
        "health_label": health_label,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),

        # Pillar 1: Volume
        "volume": {
            "total_rows": total_rows,
            "expected_rows": expected_rows,
            "volume_ok": volume_ok,
            "volume_pct": round(total_rows / expected_rows * 100, 1) if expected_rows > 0 else 0.0,
        },

        # Pillar 2: Freshness
        "freshness": {
            "event_arrival_latency_avg_ms": avg_latency,
            "event_arrival_latencies": event_arrival_latencies[:50],  # keep first 50
            "days_since_last_visit": days_since,
            "freshness_ok": freshness_ok,
            "freshness_max_days": freshness_max_days,
        },

        # Pillar 3: Schema
        "schema": {
            "null_stats": null_stats,
            "schema_issues": schema_issues,
            "duplicate_count": dup_count,
            "duplicate_pct": dup_pct,
        },

        # Pillar 4: Distribution
        "distribution": {
            "outlier_stats": outlier_stats,
            "severity_distribution": severity_dist,
            "side_effect_distribution": side_effect_dist,
        },

        # Pillar 5: Lineage
        "lineage": {
            "drift_results": drift_results,
            "data_sources": data_sources,
            "baseline_loaded": os.path.exists(baseline_path),
        },

        # Streaming metadata
        "streaming": {
            "events_in_window": streaming_metadata.get("events_received", total_rows),
            "events_valid": streaming_metadata.get("events_valid", total_rows),
            "events_invalid": streaming_metadata.get("events_invalid", 0),
            "schema_errors_in_stream": len(streaming_metadata.get("schema_errors", [])),
            "consumer_lag_avg": streaming_metadata.get("consumer_lag_avg", 0),
        },

        # Log summary
        "log_summary": {
            "total_warnings": total_warnings,
            "total_errors": total_errors,
            "total_info": log_counts["INFO"],
        },
    }

    # ── 10. Write output files ────────────────────────────────────────────────
    metrics_path = os.path.join(output_dir, "rolling_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, cls=_NumpyJSONEncoder)

    return metrics


# ─── Private ─────────────────────────────────────────────────────────────────

def _minimal_metrics(run_id: str, output_dir: str) -> Dict[str, Any]:
    metrics = {
        "run_id": run_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": 0,
        "health_score": 0.0,
        "health_label": "Poor",
        "anomalies": ["Empty event buffer"],
        "anomaly_count": 1,
        "volume": {"total_rows": 0, "expected_rows": 500, "volume_ok": False, "volume_pct": 0.0},
        "freshness": {"event_arrival_latency_avg_ms": 0.0, "event_arrival_latencies": [], "days_since_last_visit": 999, "freshness_ok": False},
        "schema": {"null_stats": {}, "schema_issues": ["No data"], "duplicate_count": 0, "duplicate_pct": 0.0},
        "distribution": {"outlier_stats": {}, "severity_distribution": {}, "side_effect_distribution": {}},
        "lineage": {"drift_results": {}, "data_sources": [], "baseline_loaded": False},
        "streaming": {"events_in_window": 0, "events_valid": 0, "events_invalid": 0, "schema_errors_in_stream": 0, "consumer_lag_avg": 0},
        "log_summary": {"total_warnings": 0, "total_errors": 1, "total_info": 0},
    }
    path = os.path.join(output_dir, "rolling_metrics.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, cls=_NumpyJSONEncoder)
    return metrics
