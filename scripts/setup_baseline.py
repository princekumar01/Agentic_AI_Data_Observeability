"""
scripts/setup_baseline.py
─────────────────────────────────────────────────────
One-time setup: reads data/clinical/clinical_trial_data.csv
and writes config/baseline_metrics.json for KS-test drift detection.

Run ONCE before the first pipeline execution:
    python scripts/setup_baseline.py

Saves:
    config/baseline_metrics.json   — baseline distributions
    config/setup_complete.json     — timestamp record
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml


CONFIG_PATH = "config.yaml"
BASELINE_OUTPUT = "config/baseline_metrics.json"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"[setup_baseline] WARNING: {CONFIG_PATH} not found — using defaults")
        return {}
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh) or {}


def main() -> None:
    cfg = load_config()
    csv_dir = cfg.get("data", {}).get("csv_directory", "data/clinical")
    csv_file = cfg.get("data", {}).get("csv_filename", "clinical_trial_data.csv")
    csv_path = os.path.join(csv_dir, csv_file)
    numeric_cols = cfg.get("preprocessing", {}).get("numeric_columns", ["age", "glucose_level"])
    expected_cols = cfg.get("validation", {}).get("expected_columns", [
        "patient_id", "patient_name", "age", "gender", "diagnosis",
        "treatment_group", "visit_date", "glucose_level", "side_effects", "severity",
    ])

    print(f"[setup_baseline] Reading: {csv_path}")

    # If CSV doesn't exist, generate a synthetic baseline
    if not os.path.exists(csv_path):
        print(f"[setup_baseline] CSV not found — generating synthetic baseline (500 rows, scenario=normal)")
        try:
            from scripts.generate_synthetic_data import generate_dataset
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scripts.generate_synthetic_data import generate_dataset

        records = generate_dataset(scenario="normal", rows=500)
        os.makedirs(csv_dir, exist_ok=True)
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False)
        print(f"[setup_baseline] Synthetic CSV written to {csv_path}")
    else:
        df = pd.read_csv(csv_path, on_bad_lines="skip")

    df.columns = [c.lower().strip() for c in df.columns]
    print(f"[setup_baseline] Loaded {len(df)} rows × {len(df.columns)} columns")

    # ── Build baseline metrics ────────────────────────────────────────────────
    distributions: dict = {}
    for col in numeric_cols:
        if col not in df.columns:
            print(f"[setup_baseline] WARNING: column '{col}' not in CSV — skipping")
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        distributions[col] = series.tolist()
        print(f"[setup_baseline]   {col}: {len(series)} values, mean={series.mean():.2f}, std={series.std():.2f}")

    # Null rates per column
    null_rates: dict = {}
    for col in expected_cols:
        if col in df.columns:
            null_rates[col] = round(df[col].isna().mean() * 100, 2)

    # Severity distribution
    severity_dist: dict = {}
    if "severity" in df.columns:
        severity_dist = df["severity"].value_counts().to_dict()

    baseline = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": csv_path,
        "row_count": len(df),
        "numeric_columns": numeric_cols,
        "distributions": distributions,
        "null_rates": null_rates,
        "severity_distribution": severity_dist,
        "schema_version": "1.0",
    }

    os.makedirs("config", exist_ok=True)
    with open(BASELINE_OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(baseline, fh, indent=2)

    print(f"\n[setup_baseline] ✓ Baseline metrics written to: {BASELINE_OUTPUT}")

    # Write setup_complete.json
    setup_record = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "baseline_path": BASELINE_OUTPUT,
        "source_csv": csv_path,
        "row_count": len(df),
    }
    with open("config/setup_complete.json", "w") as fh:
        json.dump(setup_record, fh, indent=2)

    print("[setup_baseline] ✓ Setup complete. You may now run the pipeline.\n")


if __name__ == "__main__":
    main()
