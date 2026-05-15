"""
preprocessing_service.py
Full CSV analysis across all 5 observability pillars using Pandas.
Simultaneously generates the ETL log file (etl_run.log) capturing every
runtime event, warning, and error during execution.

The ETL log is a runtime artifact — it does NOT exist before the pipeline runs.
"""

import os
import re
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from scipy.stats import ks_2samp
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Logger setup
# ─────────────────────────────────────────────────────────────────────────────

def _setup_etl_logger(run_id: str, output_dir: str) -> tuple:
    """
    Configure a dedicated file logger for this pipeline run.
    Returns (logger, log_path).
    """
    log_path = os.path.join(output_dir, "etl_run.log")
    logger = logging.getLogger(f"etl_{run_id}")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on re-runs in the same process
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger, log_path


# ─────────────────────────────────────────────────────────────────────────────
# Main preprocessing entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_preprocessing(csv_path: str, run_id: str, config: dict, output_dir: str) -> dict:
    """
    Execute all preprocessing steps and generate the ETL log.

    Returns:
        {
            "metrics": dict,       # Full Metrics JSON
            "log_path": str,       # Absolute path to etl_run.log
        }
    """
    logger, log_path = _setup_etl_logger(run_id, output_dir)
    run_timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"=" * 60)
    logger.info(f"ETL Pipeline started | run_id={run_id}")
    logger.info(f"Timestamp: {run_timestamp}")
    logger.info(f"CSV source: {csv_path}")
    logger.info(f"=" * 60)

    metrics = {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "csv_path": csv_path,
    }

    # Load baseline metrics
    baseline = _load_baseline(config, logger)

    # ── Step 1: Load DataFrame ───────────────────────────────────────────────
    logger.info("[STEP 1] Loading CSV into Pandas DataFrame...")
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"[STEP 1] CSV loaded successfully. Shape: {df.shape} "
                    f"({df.shape[0]} rows, {df.shape[1]} columns)")
    except Exception as exc:
        logger.error(f"[STEP 1] FATAL — Failed to load CSV: {exc}")
        raise

    # ── Step 2: Volume Check (Pillar: Volume) ────────────────────────────────
    logger.info("[STEP 2] Volume check — comparing row count to expected...")
    pillar_volume = _check_volume(df, config, logger)
    metrics["pillar_volume"] = pillar_volume

    # ── Step 3: Freshness (Pillar: Freshness) ────────────────────────────────
    logger.info("[STEP 3] Freshness check — validating visit dates...")
    pillar_freshness = _check_freshness(df, config, logger)
    metrics["pillar_freshness"] = pillar_freshness

    # ── Step 4: Null Detection (Pillar: Schema/Quality) ──────────────────────
    logger.info("[STEP 4] Null detection — scanning all columns...")
    null_report = _check_nulls(df, config, logger)

    # ── Step 5: Duplicate Detection (Pillar: Quality) ────────────────────────
    logger.info("[STEP 5] Duplicate detection — checking patient_id uniqueness...")
    duplicate_count = _check_duplicates(df, logger)

    # ── Step 6: Dtype Verification (Pillar: Schema) ──────────────────────────
    logger.info("[STEP 6] Dtype verification — validating column types...")
    dtype_checks = _check_dtypes(df, logger)

    metrics["pillar_schema"] = {
        "expected_columns": config["validation"]["expected_columns"],
        "actual_columns": list(df.columns),
        "missing_columns": [
            c for c in config["validation"]["expected_columns"] if c not in df.columns
        ],
        "extra_columns": [
            c for c in df.columns if c not in config["validation"]["expected_columns"]
        ],
        "dtype_checks": dtype_checks,
        "null_report": null_report,
        "duplicate_patient_ids": int(duplicate_count),
    }

    # ── Step 7: Outlier Detection (Pillar: Distribution) ─────────────────────
    logger.info("[STEP 7] Outlier detection — IQR method on numeric columns...")
    outlier_stats = _detect_outliers(df, config, logger)

    # ── Step 8: Severity & Side Effect Analysis (Pillar: Distribution) ───────
    logger.info("[STEP 8] Severity distribution and side effect analysis...")
    severity_stats = _analyze_severity(df, baseline, logger)

    # ── Step 9: Drift Detection (Pillar: Distribution) ───────────────────────
    logger.info("[STEP 9] Drift detection — KS-test vs baseline distribution...")
    drift_results = _detect_drift(df, baseline, config, logger)

    metrics["pillar_distribution"] = {
        **outlier_stats,
        **severity_stats,
        "drift_detection": drift_results,
    }

    # ── Step 10: Lineage metadata (Pillar: Lineage) ──────────────────────────
    logger.info("[STEP 10] Finalising lineage metadata...")

    # Count warnings and errors logged so far by scanning log file
    warning_count, error_count = _count_log_levels(log_path)

    metrics["pillar_lineage"] = {
        "etl_log_path": log_path,
        "warning_count": warning_count,
        "error_count": error_count,
    }

    # ── Compute overall health score ─────────────────────────────────────────
    anomalies_detected = _collect_anomalies(metrics)
    anomaly_count = len(anomalies_detected)
    health_score = max(0, 100 - (anomaly_count * 10))

    metrics["overall_health_score"] = health_score
    metrics["anomaly_count"] = anomaly_count
    metrics["anomalies_detected"] = anomalies_detected

    logger.info(f"=" * 60)
    logger.info(f"Preprocessing completed | Health Score: {health_score}/100")
    logger.info(f"Anomalies detected: {anomaly_count} → {anomalies_detected}")
    logger.info(f"Metrics JSON generated for run_id: {run_id}")
    logger.info(f"=" * 60)

    # Flush and close logger handlers to ensure file is fully written
    for handler in logger.handlers:
        handler.flush()
        handler.close()
    logger.handlers.clear()

    return {"metrics": metrics, "log_path": log_path}


# ─────────────────────────────────────────────────────────────────────────────
# Individual check functions
# ─────────────────────────────────────────────────────────────────────────────

def _load_baseline(config: dict, logger: logging.Logger) -> dict:
    path = config["data"]["baseline_metrics_path"]
    try:
        with open(path, "r") as f:
            baseline = json.load(f)
        logger.info(f"Baseline metrics loaded from: {path}")
        return baseline
    except Exception as exc:
        logger.warning(f"Could not load baseline metrics from '{path}': {exc}. "
                       f"Using hardcoded defaults.")
        return {
            "expected_row_count": 500,
            "glucose_level_mean": 150.0,
            "glucose_level_std": 45.0,
            "age_mean": 55.0,
            "age_std": 15.0,
            "severity_distribution": {
                "Low": 0.35, "Medium": 0.30, "High": 0.20, "Critical": 0.15
            },
        }


def _check_volume(df: pd.DataFrame, config: dict, logger: logging.Logger) -> dict:
    row_count = len(df)
    expected = config["data"]["expected_row_count"]
    delta_pct = abs(row_count - expected) / max(expected, 1) * 100
    volume_anomaly = delta_pct > 5.0

    if volume_anomaly:
        logger.warning(
            f"Volume anomaly: row_count={row_count}, expected={expected}, "
            f"delta={delta_pct:.2f}%"
        )
    else:
        logger.info(
            f"Volume check passed: row_count={row_count}, expected={expected}, "
            f"delta={delta_pct:.2f}%"
        )

    return {
        "row_count": int(row_count),
        "expected_row_count": int(expected),
        "volume_delta_pct": round(float(delta_pct), 2),
        "volume_anomaly": volume_anomaly,
    }


def _check_freshness(df: pd.DataFrame, config: dict, logger: logging.Logger) -> dict:
    date_col = config["validation"]["date_column"]
    max_days = config["data"]["freshness_max_days"]
    now = datetime.now(timezone.utc)
    freshness_ok = True
    most_recent = None
    days_since = None

    try:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        max_date = dates.max()
        if pd.notna(max_date):
            most_recent = str(max_date.date())
            days_since = (now.date() - max_date.date()).days
            freshness_ok = days_since <= max_days
            if not freshness_ok:
                logger.warning(
                    f"Data freshness issue: most recent date={most_recent}, "
                    f"{days_since} days ago (threshold={max_days})"
                )
            else:
                logger.info(
                    f"Data freshness OK: most recent date={most_recent}, "
                    f"{days_since} days ago"
                )
    except Exception as exc:
        logger.warning(f"Freshness check failed: {exc}")

    return {
        "most_recent_visit_date": most_recent,
        "days_since_last_visit": days_since,
        "freshness_max_days": max_days,
        "freshness_ok": freshness_ok,
    }


def _check_nulls(df: pd.DataFrame, config: dict, logger: logging.Logger) -> dict:
    threshold = config["preprocessing"]["null_threshold_pct"]
    null_report = {}
    total_rows = len(df)

    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        null_pct = round(null_count / max(total_rows, 1) * 100, 2)
        null_report[col] = {"null_count": null_count, "null_pct": null_pct}

        if null_pct > threshold:
            logger.warning(
                f"High null rate in column '{col}': {null_pct:.2f}% "
                f"({null_count}/{total_rows} rows)"
            )
        else:
            logger.info(f"Null check OK for '{col}': {null_pct:.2f}%")

    return null_report


def _check_duplicates(df: pd.DataFrame, logger: logging.Logger) -> int:
    if "patient_id" not in df.columns:
        logger.warning("Duplicate check skipped — 'patient_id' column not found")
        return 0

    duplicate_count = int(df.duplicated(subset=["patient_id"]).sum())
    if duplicate_count > 0:
        logger.warning(
            f"Duplicate patient records detected: {duplicate_count} rows "
            f"share an existing patient_id"
        )
    else:
        logger.info("Duplicate check passed: all patient_ids are unique")
    return duplicate_count


def _check_dtypes(df: pd.DataFrame, logger: logging.Logger) -> dict:
    dtype_checks = {}

    # age — numeric
    col = "age"
    if col in df.columns:
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        dtype_checks[col] = {
            "expected": "numeric",
            "actual": str(df[col].dtype),
            "passed": is_numeric,
        }
        if not is_numeric:
            logger.error(f"Dtype mismatch in '{col}': expected numeric, got {df[col].dtype}")
        else:
            logger.info(f"Dtype check passed for '{col}': {df[col].dtype}")

    # glucose_level — numeric
    col = "glucose_level"
    if col in df.columns:
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        dtype_checks[col] = {
            "expected": "numeric",
            "actual": str(df[col].dtype),
            "passed": is_numeric,
        }
        if not is_numeric:
            logger.error(f"Dtype mismatch in '{col}': expected numeric, got {df[col].dtype}")
        else:
            logger.info(f"Dtype check passed for '{col}': {df[col].dtype}")

    # visit_date — parseable as date
    col = "visit_date"
    if col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            invalid_count = int(parsed.isnull().sum())
            passed = invalid_count == 0
            dtype_checks[col] = {
                "expected": "date (YYYY-MM-DD)",
                "actual": str(df[col].dtype),
                "passed": passed,
                "invalid_count": invalid_count,
            }
            if not passed:
                logger.error(
                    f"Dtype issue in '{col}': {invalid_count} rows could not be "
                    f"parsed as dates"
                )
            else:
                logger.info(f"Dtype check passed for '{col}': all rows parse as dates")
        except Exception as exc:
            logger.error(f"Dtype check failed for '{col}': {exc}")

    # blood_pressure — pattern NNN/NN
    col = "blood_pressure"
    if col in df.columns:
        pattern = re.compile(r"^\d{2,3}/\d{2,3}$")
        invalid_mask = df[col].astype(str).apply(
            lambda x: not bool(pattern.match(x.strip()))
        )
        invalid_count = int(invalid_mask.sum())
        passed = invalid_count == 0
        dtype_checks[col] = {
            "expected": "pattern NNN/NN",
            "actual": str(df[col].dtype),
            "passed": passed,
            "invalid_count": invalid_count,
        }
        if not passed:
            logger.warning(
                f"Pattern mismatch in '{col}': {invalid_count} rows do not match "
                f"expected NNN/NN format"
            )
        else:
            logger.info(f"Dtype/pattern check passed for '{col}'")

    return dtype_checks


def _detect_outliers(df: pd.DataFrame, config: dict, logger: logging.Logger) -> dict:
    multiplier = config["preprocessing"]["outlier_iqr_multiplier"]
    result = {}

    for col in ["glucose_level", "age"]:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - (multiplier * iqr)
        upper = q3 + (multiplier * iqr)
        outlier_mask = (series < lower) | (series > upper)
        outlier_count = int(outlier_mask.sum())

        result[col] = {
            "mean": round(float(series.mean()), 2),
            "std": round(float(series.std()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "outlier_count": outlier_count,
            "outlier_lower_bound": round(lower, 2),
            "outlier_upper_bound": round(upper, 2),
        }

        if outlier_count > 0:
            logger.warning(
                f"Outliers in '{col}': count={outlier_count}, "
                f"bounds=[{lower:.2f}, {upper:.2f}]"
            )
        else:
            logger.info(f"No outliers detected in '{col}' (bounds=[{lower:.2f}, {upper:.2f}])")

    return result


def _analyze_severity(df: pd.DataFrame, baseline: dict, logger: logging.Logger) -> dict:
    result = {}

    if "severity" in df.columns:
        severity_dist = df["severity"].value_counts(normalize=True).round(4).to_dict()
        severity_counts = df["severity"].value_counts().to_dict()
        result["severity_distribution"] = {k: float(v) for k, v in severity_dist.items()}
        result["severity_counts"] = {k: int(v) for k, v in severity_counts.items()}

        baseline_dist = baseline.get("severity_distribution", {})
        for level, expected_pct in baseline_dist.items():
            actual_pct = severity_dist.get(level, 0)
            if abs(actual_pct - expected_pct) > 0.10:
                logger.warning(
                    f"Severity distribution shift for '{level}': "
                    f"expected={expected_pct:.2f}, actual={actual_pct:.2f}"
                )
            else:
                logger.info(
                    f"Severity '{level}' distribution OK: "
                    f"expected={expected_pct:.2f}, actual={actual_pct:.2f}"
                )

        # Critical event rate
        total_critical = int((df["severity"] == "Critical").sum())
        critical_pct = round(total_critical / max(len(df), 1) * 100, 2)
        result["critical_event_pct"] = critical_pct

        if critical_pct > 20:
            logger.warning(
                f"High critical event rate: {critical_pct:.2f}% of patients "
                f"have Critical severity"
            )
        else:
            logger.info(f"Critical event rate: {critical_pct:.2f}%")

    if "side_effect" in df.columns:
        side_effect_counts = df["side_effect"].value_counts().to_dict()
        result["side_effect_counts"] = {k: int(v) for k, v in side_effect_counts.items()}
        logger.info(f"Side effects recorded: {len(side_effect_counts)} unique types")

    return result


def _detect_drift(
    df: pd.DataFrame, baseline: dict, config: dict, logger: logging.Logger
) -> dict:
    threshold = config["preprocessing"]["drift_ks_pvalue_threshold"]
    drift_results = {}

    for col in config["preprocessing"]["numeric_columns"]:
        if col not in df.columns:
            continue

        current_values = pd.to_numeric(df[col], errors="coerce").dropna().values

        mean_key = f"{col}_mean"
        std_key = f"{col}_std"
        if mean_key not in baseline or std_key not in baseline:
            logger.warning(f"Drift detection skipped for '{col}': no baseline stats found")
            continue

        rng = np.random.default_rng(42)
        baseline_sample = rng.normal(
            loc=baseline[mean_key],
            scale=baseline[std_key],
            size=len(current_values),
        )

        try:
            statistic, p_value = ks_2samp(current_values, baseline_sample)
            drift_detected = bool(p_value < threshold)

            drift_results[col] = {
                "ks_statistic": round(float(statistic), 4),
                "p_value": round(float(p_value), 4),
                "drift_detected": drift_detected,
            }

            if drift_detected:
                logger.warning(
                    f"Distribution DRIFT detected in '{col}': "
                    f"KS={statistic:.4f}, p-value={p_value:.4f} "
                    f"(threshold={threshold})"
                )
            else:
                logger.info(
                    f"No drift in '{col}': KS={statistic:.4f}, p-value={p_value:.4f}"
                )
        except Exception as exc:
            logger.error(f"Drift detection failed for '{col}': {exc}")

    return drift_results


def _count_log_levels(log_path: str) -> tuple:
    """Count WARNING and ERROR lines in the log file."""
    warning_count = 0
    error_count = 0
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "| WARNING" in line:
                    warning_count += 1
                elif "| ERROR" in line or "| CRITICAL" in line:
                    error_count += 1
    except Exception:
        pass
    return warning_count, error_count


def _collect_anomalies(metrics: dict) -> list:
    """Build a list of anomaly labels from the metrics dict."""
    anomalies = []

    vol = metrics.get("pillar_volume", {})
    if vol.get("volume_anomaly"):
        anomalies.append("volume_delta")

    schema = metrics.get("pillar_schema", {})
    if schema.get("missing_columns"):
        anomalies.append("missing_columns")
    if schema.get("duplicate_patient_ids", 0) > 0:
        anomalies.append("duplicate_patient_ids")

    null_report = schema.get("null_report", {})
    for col, info in null_report.items():
        if info.get("null_pct", 0) > 5.0:
            anomalies.append(f"high_nulls_{col}")

    dist = metrics.get("pillar_distribution", {})
    for col in ["glucose_level", "age"]:
        if dist.get(col, {}).get("outlier_count", 0) > 0:
            anomalies.append(f"{col}_outliers")

    for col, drift in dist.get("drift_detection", {}).items():
        if drift.get("drift_detected"):
            anomalies.append(f"drift_{col}")

    freshness = metrics.get("pillar_freshness", {})
    if not freshness.get("freshness_ok", True):
        anomalies.append("data_freshness")

    lineage = metrics.get("pillar_lineage", {})
    if lineage.get("error_count", 0) > 0:
        anomalies.append("etl_errors")

    return anomalies
