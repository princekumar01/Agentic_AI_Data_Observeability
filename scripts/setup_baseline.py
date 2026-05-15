"""
setup_baseline.py
One-time script to generate baseline_metrics.json from the CSV dataset.
Run this once before starting the application:

    python scripts/setup_baseline.py

This computes the baseline statistics (mean, std, distributions) that the
KS-test drift detection compares against in every subsequent pipeline run.
"""

import os
import sys
import json

import pandas as pd
import numpy as np
import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_baseline():
    # Load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    csv_dir      = config["data"]["csv_directory"]
    csv_filename = config["data"]["csv_filename"]
    csv_path     = os.path.join(csv_dir, csv_filename)
    output_path  = config["data"]["baseline_metrics_path"]

    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found at '{csv_path}'")
        print(f"Place the CSV file there first, then re-run this script.")
        sys.exit(1)

    print(f"Reading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    baseline = {}

    # ── Row count ─────────────────────────────────────────────────────────────
    baseline["expected_row_count"] = len(df)
    print(f"Row count: {len(df)}")

    # ── Numeric columns ───────────────────────────────────────────────────────
    for col in config["preprocessing"]["numeric_columns"]:
        if col not in df.columns:
            print(f"WARNING: Column '{col}' not found in CSV — skipping.")
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        baseline[f"{col}_mean"] = round(float(series.mean()), 4)
        baseline[f"{col}_std"]  = round(float(series.std()), 4)
        print(f"{col}: mean={baseline[f'{col}_mean']}, std={baseline[f'{col}_std']}")

    # ── Severity distribution ─────────────────────────────────────────────────
    if "severity" in df.columns:
        dist = df["severity"].value_counts(normalize=True).round(4)
        baseline["severity_distribution"] = {k: float(v) for k, v in dist.items()}
        print(f"Severity distribution: {baseline['severity_distribution']}")
    else:
        print("WARNING: 'severity' column not found — skipping distribution.")

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"\nBaseline metrics saved to: {output_path}")
    print("You can now start the application.")
    return baseline


if __name__ == "__main__":
    generate_baseline()
