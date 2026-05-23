"""
scripts/generate_synthetic_data.py
─────────────────────────────────────────────────────
Synthetic clinical trial data generator.

Supports scenarios:
  normal        — realistic healthy distribution
  high_nulls    — elevated null rates across all columns
  many_outliers — glucose_level and age outliers injected
  drift         — values shifted to simulate distribution drift
  mixed         — combination of all anomaly types

All names generated via Faker — no real patient data used.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from faker import Faker

_faker = Faker()
_faker.seed_instance(42)
random.seed(42)

DIAGNOSES = [
    "Type 2 Diabetes", "Hypertension", "Coronary Artery Disease",
    "Chronic Kidney Disease", "Heart Failure", "Atrial Fibrillation",
    "COPD", "Asthma", "Obesity", "Metabolic Syndrome",
]
TREATMENT_GROUPS = ["Control", "Treatment A", "Treatment B", "Placebo"]
GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
SIDE_EFFECTS_POOL = [
    "None", "Nausea", "Headache", "Fatigue", "Dizziness",
    "Rash", "Insomnia", "Palpitations", "Dry mouth", "Constipation",
]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS_NORMAL = [0.45, 0.35, 0.15, 0.05]
SEVERITY_WEIGHTS_MIXED = [0.20, 0.30, 0.30, 0.20]


def _random_visit_date(drift_days: int = 0) -> str:
    base = datetime.now() - timedelta(days=random.randint(0, 30) + drift_days)
    return base.strftime("%Y-%m-%d")


def _normal_glucose() -> float:
    return round(random.gauss(100.0, 15.0), 2)


def _outlier_glucose() -> float:
    # Either very low or very high
    return round(random.choice([
        random.gauss(20.0, 5.0),
        random.gauss(450.0, 30.0),
    ]), 2)


def _outlier_age() -> int:
    return random.choice([random.randint(0, 5), random.randint(120, 145)])


def _generate_row(
    idx: int,
    scenario: str,
    null_rate: float,
    outlier_pct: float,
    drift_days: int,
    is_duplicate: bool = False,
) -> Dict[str, Any]:
    """Generate one synthetic patient record."""

    def _maybe_null(value: Any) -> Any:
        return None if random.random() < null_rate else value

    patient_id = f"PT_{idx:05d}" if not is_duplicate else f"PT_{max(1, idx - 1):05d}"
    patient_name = _faker.name()
    age: Any = random.randint(18, 85)
    gender: Any = random.choice(GENDERS)
    diagnosis: Any = random.choice(DIAGNOSES)
    treatment_group: Any = random.choice(TREATMENT_GROUPS)
    visit_date: Any = _random_visit_date(drift_days)
    side_effects: Any = random.choice(SIDE_EFFECTS_POOL)

    # Glucose level
    is_outlier = random.random() < outlier_pct
    if is_outlier and scenario in ("many_outliers", "mixed"):
        glucose_level: Any = _outlier_glucose()
    elif scenario == "drift":
        glucose_level = round(random.gauss(140.0, 20.0), 2)  # shifted mean
    else:
        glucose_level = _normal_glucose()

    # Age outliers
    if is_outlier and scenario in ("many_outliers", "mixed"):
        age = _outlier_age()

    # Severity
    if scenario == "mixed":
        severity: Any = random.choices(SEVERITIES, SEVERITY_WEIGHTS_MIXED)[0]
    else:
        severity = random.choices(SEVERITIES, SEVERITY_WEIGHTS_NORMAL)[0]

    # Apply nulls for high_nulls scenario
    if scenario in ("high_nulls", "mixed"):
        null_rate_effective = max(null_rate, 0.15)
    else:
        null_rate_effective = null_rate

    return {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "age": _maybe_null(age) if scenario in ("high_nulls", "mixed") else age,
        "gender": _maybe_null(gender) if scenario in ("high_nulls", "mixed") else gender,
        "diagnosis": _maybe_null(diagnosis) if null_rate_effective > 0 else diagnosis,
        "treatment_group": _maybe_null(treatment_group) if null_rate_effective > 0 else treatment_group,
        "visit_date": _maybe_null(visit_date) if null_rate_effective > 0 else visit_date,
        "glucose_level": _maybe_null(glucose_level) if null_rate_effective > 0 else glucose_level,
        "side_effects": _maybe_null(side_effects) if null_rate_effective > 0 else side_effects,
        "severity": _maybe_null(severity) if null_rate_effective > 0 else severity,
    }


def generate_dataset(
    scenario: str = "normal",
    rows: int = 500,
    null_rate: float = 0.02,
    outlier_pct: float = 0.05,
    date_drift_days: int = 0,
    duplicate_rate: float = 0.01,
) -> List[Dict[str, Any]]:
    """
    Generate a synthetic clinical trial dataset.

    Parameters
    ----------
    scenario       : Data scenario — normal | high_nulls | many_outliers | drift | mixed
    rows           : Number of rows to generate
    null_rate      : Base probability of a field being null (0.0–1.0)
    outlier_pct    : Probability of numeric fields having outlier values
    date_drift_days: Days to shift visit_date backwards (simulate stale data)
    duplicate_rate : Probability of a row being a duplicate patient_id

    Returns
    -------
    List[Dict] — each dict has the 10 required clinical trial columns
    """
    records: List[Dict[str, Any]] = []
    for i in range(1, rows + 1):
        is_dup = random.random() < duplicate_rate and i > 1
        row = _generate_row(
            idx=i,
            scenario=scenario,
            null_rate=null_rate,
            outlier_pct=outlier_pct,
            drift_days=date_drift_days,
            is_duplicate=is_dup,
        )
        records.append(row)
    return records


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate synthetic clinical trial data")
    parser.add_argument("--scenario", default="normal",
                        choices=["normal", "high_nulls", "many_outliers", "drift", "mixed"])
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--null-rate", type=float, default=0.02)
    parser.add_argument("--outlier-pct", type=float, default=0.05)
    parser.add_argument("--drift-days", type=int, default=0)
    parser.add_argument("--duplicate-rate", type=float, default=0.01)
    parser.add_argument("--output", default="data/clinical/clinical_trial_data.csv")
    args = parser.parse_args()

    import pandas as pd
    import os

    data = generate_dataset(
        scenario=args.scenario,
        rows=args.rows,
        null_rate=args.null_rate,
        outlier_pct=args.outlier_pct,
        date_drift_days=args.drift_days,
        duplicate_rate=args.duplicate_rate,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df = pd.DataFrame(data)
    df.to_csv(args.output, index=False)

    stats = {
        "rows": len(data),
        "scenario": args.scenario,
        "null_rate_avg": round(df.isnull().mean().mean(), 4),
        "severity_distribution": df["severity"].value_counts().to_dict(),
        "saved_to": args.output,
    }
    print(json.dumps(stats, indent=2))
