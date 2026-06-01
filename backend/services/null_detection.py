"""
Shared null / missing-value detection for clinical trial records.

Treats pandas NaN, JSON null, empty strings, and common sentinel tokens as missing.
Does not treat numeric zero as missing.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

# Alternate CSV / API column names → canonical pipeline column names
COLUMN_ALIASES: Dict[str, str] = {
    "side_effect": "side_effects",
    "medication": "treatment_group",
}

NULLISH_STRING_TOKENS = frozenset({
    "",
    "nan",
    "none",
    "null",
    "na",
    "n/a",
    "#n/a",
    "nil",
    "-",
})


def is_nullish_scalar(value: Any) -> bool:
    """Return True if a single cell value should count as null/missing."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in NULLISH_STRING_TOKENS
    return False


def count_nullish(series: pd.Series) -> int:
    """Count null/missing values in a DataFrame column."""
    if series.empty:
        return 0
    if pd.api.types.is_numeric_dtype(series):
        return int(series.isna().sum())
    mask = series.isna()
    if (~mask).any():
        str_vals = series[~mask].astype(str).str.strip().str.lower()
        extra = str_vals.isin(NULLISH_STRING_TOKENS)
        mask = mask.copy()
        mask.loc[extra.index[extra]] = True
    return int(mask.sum())


def normalize_record_columns(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lowercase/strip keys and apply COLUMN_ALIASES so source files map to
    expected_columns names (e.g. side_effect → side_effects).
    """
    out: Dict[str, Any] = {}
    for key, value in row.items():
        out[str(key).lower().strip()] = value
    for alias, canonical in COLUMN_ALIASES.items():
        if canonical not in out and alias in out:
            out[canonical] = out[alias]
    return out


def preserve_optional_str(value: Any) -> Optional[str]:
    if is_nullish_scalar(value):
        return None
    return str(value).strip()


def preserve_optional_int(value: Any) -> Optional[int]:
    if is_nullish_scalar(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def preserve_optional_float(value: Any) -> Optional[float]:
    if is_nullish_scalar(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_record_field(row: Dict[str, Any], field: str) -> Any:
    """Read a canonical field from a normalised row dict."""
    if field in row:
        return row[field]
    return None
