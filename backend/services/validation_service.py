"""
backend/services/validation_service.py
─────────────────────────────────────────────────────
Pre-Ingest Validation Gate.
Hard blocks disable the Run button.
Soft warnings are shown but do not block.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd


REQUIRED_COLUMNS = [
    "patient_id",
    "patient_name",
    "age",
    "gender",
    "diagnosis",
    "treatment_group",
    "visit_date",
    "glucose_level",
    "side_effects",
    "severity",
]

VALID_SEVERITIES = {"Low", "Medium", "High", "Critical"}


def run_preflight(
    csv_path: str,
    run_id: str,
    config: Dict[str, Any],
    output_dir: str,
) -> Dict[str, Any]:
    """
    Execute all hard-block and soft-warning checks against csv_path.
    Writes preflight_report.json to output_dir.
    Returns the report dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    hard_blocks: List[Dict] = []
    soft_warnings: List[Dict] = []
    cross_field_violations: List[Dict] = []
    row_count = 0
    checked_at = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Encoding check ────────────────────────────────────────────────
    try:
        with open(csv_path, "rb") as fh:
            raw = fh.read()
        raw.decode("utf-8")
    except UnicodeDecodeError:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "wrong_file_encoding",
            "column": None,
            "message": "File is not UTF-8 encoded.",
            "detail": "Re-save the CSV as UTF-8.",
        })
        return _report(run_id, checked_at, hard_blocks, soft_warnings, cross_field_violations, 0, output_dir)
    except FileNotFoundError:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "file_not_found",
            "column": None,
            "message": f"File not found: {csv_path}",
            "detail": "Upload a file before running preflight.",
        })
        return _report(run_id, checked_at, hard_blocks, soft_warnings, cross_field_violations, 0, output_dir)

    # ── Step 2: Parse ─────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(csv_path, encoding="utf-8", on_bad_lines="skip")
    except Exception as exc:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "zero_valid_rows",
            "column": None,
            "message": f"Could not parse CSV: {exc}",
            "detail": str(exc),
        })
        return _report(run_id, checked_at, hard_blocks, soft_warnings, cross_field_violations, 0, output_dir)

    row_count = len(df)

    # Hard: zero rows
    if row_count == 0:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "zero_valid_rows",
            "column": None,
            "message": "File contains no parseable rows.",
            "detail": "Check that the file has data rows.",
        })

    # ── Step 3: Missing columns ───────────────────────────────────────────────
    df_cols_lower = {c.lower().strip() for c in df.columns}
    missing = [c for c in REQUIRED_COLUMNS if c.lower() not in df_cols_lower]
    if missing:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "missing_required_values",
            "column": ", ".join(missing),
            "message": f"Required columns missing: {', '.join(missing)}",
            "detail": f"Add the following columns: {', '.join(missing)}",
        })

    if hard_blocks:
        return _report(run_id, checked_at, hard_blocks, soft_warnings, cross_field_violations, row_count, output_dir)

    # Normalise column names
    df.columns = [c.lower().strip() for c in df.columns]

    # ── Step 4: Completely empty columns ─────────────────────────────────────
    for col in REQUIRED_COLUMNS:
        if df[col].isna().all():
            hard_blocks.append({
                "id": str(uuid.uuid4())[:8],
                "check": "completely_empty_column",
                "column": col,
                "message": f"Column '{col}' is 100% null.",
                "detail": "Provide data for this column.",
            })

    # ── Step 5: Excessive duplicates ─────────────────────────────────────────
    dup_rate = df["patient_id"].duplicated(keep=False).mean()
    if dup_rate > 0.10:
        hard_blocks.append({
            "id": str(uuid.uuid4())[:8],
            "check": "excessive_duplicates",
            "column": "patient_id",
            "message": f"Duplicate patient_id rate is {dup_rate:.1%} (threshold: 10%).",
            "detail": "Deduplicate patient_id before ingestion.",
        })

    # ── Step 6: Soft warnings ─────────────────────────────────────────────────
    null_threshold = config.get("preprocessing", {}).get("null_threshold_pct", 5.0)

    for col in REQUIRED_COLUMNS:
        null_pct = df[col].isna().mean() * 100
        if null_pct > 30:
            soft_warnings.append({
                "id": str(uuid.uuid4())[:8],
                "check": "high_null_rate",
                "column": col,
                "message": f"Column '{col}' has {null_pct:.1f}% null values (threshold: 30%).",
                "detail": f"Consider imputation or data remediation for '{col}'.",
            })

    if row_count < 100:
        soft_warnings.append({
            "id": str(uuid.uuid4())[:8],
            "check": "low_row_count",
            "column": None,
            "message": f"Only {row_count} rows found (recommended: ≥ 100).",
            "detail": "Low sample size may reduce statistical reliability.",
        })

    # Severity imbalance
    if "severity" in df.columns:
        sev_counts = df["severity"].value_counts(normalize=True)
        for sev, pct in sev_counts.items():
            if pct > 0.70:
                soft_warnings.append({
                    "id": str(uuid.uuid4())[:8],
                    "check": "severity_imbalance",
                    "column": "severity",
                    "message": f"Severity '{sev}' comprises {pct:.1%} of records (threshold: 70%).",
                    "detail": "Imbalanced severity distribution may skew agent analysis.",
                })

    # Stale dates
    if "visit_date" in df.columns:
        try:
            dates = pd.to_datetime(df["visit_date"], errors="coerce")
            valid_dates = dates.dropna()
            if len(valid_dates) > 0:
                freshness_days = config.get("data", {}).get("freshness_max_days", 7)
                max_date = valid_dates.max()
                age_days = (pd.Timestamp.now() - max_date).days
                if age_days > 20:
                    soft_warnings.append({
                        "id": str(uuid.uuid4())[:8],
                        "check": "stale_data",
                        "column": "visit_date",
                        "message": f"Most recent visit_date is {age_days} days ago (threshold: 20 days).",
                        "detail": "Verify data currency before analysis.",
                    })
        except Exception:
            pass

    # ── Step 7: Cross-field violations ────────────────────────────────────────
    # Rule: glucose_level should be numeric
    glucose_non_numeric = pd.to_numeric(df["glucose_level"], errors="coerce").isna().sum()
    if glucose_non_numeric > 0:
        cross_field_violations.append({
            "rule": "glucose_level must be numeric",
            "affected_rows": int(glucose_non_numeric),
            "example": str(df["glucose_level"].dropna().head(1).values[0]) if len(df) > 0 else None,
        })

    # Rule: age should be numeric 0-130
    age_invalid = (~pd.to_numeric(df["age"], errors="coerce").between(0, 130)).sum()
    if age_invalid > 0:
        cross_field_violations.append({
            "rule": "age must be numeric 0–130",
            "affected_rows": int(age_invalid),
            "example": None,
        })

    # Rule: severity must be from allowed values
    invalid_severity = df["severity"].dropna()
    invalid_severity = invalid_severity[~invalid_severity.isin(VALID_SEVERITIES)]
    if len(invalid_severity) > 0:
        cross_field_violations.append({
            "rule": "severity must be one of: Low, Medium, High, Critical",
            "affected_rows": int(len(invalid_severity)),
            "example": str(invalid_severity.iloc[0]) if len(invalid_severity) > 0 else None,
        })

    return _report(run_id, checked_at, hard_blocks, soft_warnings, cross_field_violations, row_count, output_dir)


# ─── Private ─────────────────────────────────────────────────────────────────

def _report(
    run_id: str,
    checked_at: str,
    hard_blocks: List[Dict],
    soft_warnings: List[Dict],
    cross_field_violations: List[Dict],
    row_count: int,
    output_dir: str,
) -> Dict[str, Any]:
    passed = len(hard_blocks) == 0
    report = {
        "run_id": run_id,
        "passed": passed,
        "checked_at": checked_at,
        "row_count": row_count,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "cross_field_violations": cross_field_violations,
    }
    path = os.path.join(output_dir, "preflight_report.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report
