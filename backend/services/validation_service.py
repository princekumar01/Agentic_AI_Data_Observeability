"""
validation_service.py
Entry validation layer — cheap, fast checks before heavy processing.
Fail early with clear errors. Does NOT load the full dataset.
"""

import re
from datetime import datetime, timezone, timedelta

import pandas as pd


def validate_entry(
    csv_path: str,
    file_modified_at: datetime,
    config: dict,
) -> dict:
    """
    Run all entry validation checks on the CSV file.

    Returns:
        {
            "passed": bool,
            "errors": list[str],   # blocking — pipeline halts on any error
            "warnings": list[str], # non-blocking — displayed on UI
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Check 1: File Freshness ──────────────────────────────────────────────
    max_hours = config["data"]["file_freshness_max_hours"]
    now_utc = datetime.now(timezone.utc)

    # Ensure file_modified_at is timezone-aware
    if file_modified_at.tzinfo is None:
        file_modified_at = file_modified_at.replace(tzinfo=timezone.utc)

    hours_since_modified = (now_utc - file_modified_at).total_seconds() / 3600

    if hours_since_modified > max_hours:
        warnings.append(
            f"File has not been updated in {hours_since_modified:.1f} hours "
            f"(threshold: {max_hours}h). Data may be stale."
        )

    # ── Check 2: Schema Validation ───────────────────────────────────────────
    expected_columns: list[str] = config["validation"]["expected_columns"]

    try:
        header_df = pd.read_csv(csv_path, nrows=0)
        actual_columns = list(header_df.columns)
    except Exception as exc:
        errors.append(f"Failed to read CSV header: {exc}")
        return {"passed": False, "errors": errors, "warnings": warnings}

    missing_cols = [c for c in expected_columns if c not in actual_columns]
    extra_cols = [c for c in actual_columns if c not in expected_columns]

    if missing_cols:
        errors.append(f"Missing required column(s): {missing_cols}")

    if extra_cols:
        warnings.append(f"Unexpected extra column(s) found: {extra_cols}")

    # ── Check 3: Data Freshness ──────────────────────────────────────────────
    date_col = config["validation"]["date_column"]
    max_days = config["data"]["freshness_max_days"]

    if date_col in actual_columns:
        try:
            date_df = pd.read_csv(
                csv_path, usecols=[date_col], parse_dates=[date_col]
            )
            max_date = date_df[date_col].max()

            if pd.notna(max_date):
                # Make max_date timezone-aware for comparison
                if max_date.tzinfo is None:
                    max_date = max_date.replace(tzinfo=timezone.utc)

                days_old = (now_utc - max_date).days

                if days_old > max_days:
                    warnings.append(
                        f"Most recent visit date ({max_date.date()}) is {days_old} days old. "
                        f"Data freshness threshold is {max_days} days."
                    )
        except Exception as exc:
            warnings.append(
                f"Could not parse '{date_col}' column for freshness check: {exc}"
            )

    passed = len(errors) == 0
    return {"passed": passed, "errors": errors, "warnings": warnings}
