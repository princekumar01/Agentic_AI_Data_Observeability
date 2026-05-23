"""
backend/services/input_service.py
─────────────────────────────────────────────────────
Handles file upload, synthetic data generation invocation,
and external API connection testing.
"""
from __future__ import annotations

import hashlib
import io
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


EXPECTED_COLUMNS = [
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


def _md5(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def _detect_encoding(file_bytes: bytes) -> str:
    """Simple encoding detection."""
    try:
        file_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def save_uploaded_file(
    file_bytes: bytes,
    filename: str,
    run_id: str,
    uploads_dir: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Save uploaded file bytes, parse it, and return
    (saved_path, file_info_dict).
    """
    os.makedirs(uploads_dir, exist_ok=True)
    safe_name = f"{run_id}_{filename}"
    saved_path = os.path.join(uploads_dir, safe_name)

    with open(saved_path, "wb") as fh:
        fh.write(file_bytes)

    encoding = _detect_encoding(file_bytes)
    file_hash = _md5(file_bytes)
    file_size_mb = round(len(file_bytes) / (1024 * 1024), 4)

    # Parse
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext in ("csv", "txt"):
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, on_bad_lines="skip")
        detected_format = "csv"
    elif ext in ("json", "jsonl"):
        df = pd.read_json(io.BytesIO(file_bytes), lines=(ext == "jsonl"))
        detected_format = "json"
    else:
        # Try CSV as fallback
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, on_bad_lines="skip")
        detected_format = "csv"

    columns = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        null_pct = round(null_count / len(df) * 100, 2) if len(df) > 0 else 0.0
        sample_val = df[col].dropna().head(1)
        sample = str(sample_val.iloc[0]) if not sample_val.empty else None
        columns.append({
            "name": col,
            "type": str(df[col].dtype),
            "sample": sample,
            "null_count": null_count,
            "null_pct": null_pct,
        })

    return saved_path, {
        "run_id": run_id,
        "filename": filename,
        "file_size_mb": file_size_mb,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "detected_format": detected_format,
        "encoding": encoding,
        "columns": columns,
        "file_hash": file_hash,
        "saved_to": saved_path,
    }


def load_csv_as_records(csv_path: str) -> List[Dict[str, Any]]:
    """Load a CSV file and return list of record dicts."""
    df = pd.read_csv(csv_path)
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def test_api_connection(
    url: str,
    auth_type: str = "None",
    token: Optional[str] = None,
    max_records: int = 500,
) -> Dict[str, Any]:
    """
    Attempt to connect to an external API and sample its response.
    API credentials are NEVER written to any log or output file.
    """
    import requests  # type: ignore

    headers: Dict[str, str] = {}
    if auth_type == "Bearer" and token:
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "API Key" and token:
        headers["X-API-Key"] = token

    try:
        t0 = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        latency_ms = round((time.time() - t0) * 1000, 1)

        if resp.status_code != 200:
            return {"connected": False, "error": f"HTTP {resp.status_code}"}

        try:
            body = resp.json()
        except Exception:
            return {"connected": False, "error": "Response is not valid JSON"}

        # Detect structure
        if isinstance(body, list):
            records = body[:max_records]
        elif isinstance(body, dict):
            # Try common keys
            for key in ("data", "results", "records", "patients", "entries"):
                if key in body and isinstance(body[key], list):
                    records = body[key][:max_records]
                    break
            else:
                records = [body]
        else:
            return {"connected": False, "error": "Unrecognised response format"}

        field_names = list(records[0].keys()) if records else []
        return {
            "connected": True,
            "endpoint": url,
            "auth_type": auth_type,
            "response_format": "json",
            "avg_latency_ms": latency_ms,
            "sample_record_count": len(records),
            "field_names": field_names,
        }
    except requests.exceptions.RequestException as exc:
        return {"connected": False, "error": str(exc)}
