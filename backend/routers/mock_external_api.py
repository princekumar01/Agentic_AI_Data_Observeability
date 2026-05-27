"""
backend/routers/mock_external_api.py
─────────────────────────────────────────────────────
Mock hospital API for testing External API (mode 3) pipeline runs.

Serves records from data/clinical/clinical_trial_data.csv as JSON.

Usage (Pipeline UI → External API):
  URL: http://localhost:8000/mock/clinical-trial/patients
  Auth: None (unless MOCK_EXTERNAL_API_TOKEN is set in .env)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Header, HTTPException, Query

from backend.services.input_service import load_csv_as_records

router = APIRouter(prefix="/mock", tags=["mock-external-api"])

_csv_cache: Dict[str, Any] = {"path": "", "mtime": 0.0, "records": []}


def _resolve_csv_path() -> str:
    csv_dir = "data/clinical"
    csv_name = "clinical_trial_data.csv"
    if os.path.exists("config.yaml"):
        try:
            with open("config.yaml") as fh:
                cfg = yaml.safe_load(fh) or {}
            data_cfg = cfg.get("data", {})
            csv_dir = data_cfg.get("csv_directory", csv_dir)
            csv_name = data_cfg.get("csv_filename", csv_name)
        except Exception:
            pass
    return os.path.join(csv_dir, csv_name)


def _load_records() -> List[Dict[str, Any]]:
    path = _resolve_csv_path()
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Clinical data file not found: {path}")

    mtime = os.path.getmtime(path)
    if _csv_cache["path"] == path and _csv_cache["mtime"] == mtime:
        return _csv_cache["records"]

    records = load_csv_as_records(path)
    _csv_cache.update({"path": path, "mtime": mtime, "records": records})
    return records


def _check_optional_auth(
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> None:
    expected = os.environ.get("MOCK_EXTERNAL_API_TOKEN", "").strip()
    if not expected:
        return

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token == expected:
            return
    if x_api_key and x_api_key.strip() == expected:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API credentials")


@router.get("/clinical-trial/patients")
def get_clinical_trial_patients(
    limit: int = Query(default=500, ge=1, le=5000, description="Max records to return"),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
  Mock external hospital API — returns clinical trial patient records as JSON.

  Response shape matches what the Kafka producer expects (`data` array).
  """
    _check_optional_auth(authorization, x_api_key)

    records = _load_records()
    sliced = records[:limit]

    return {
        "data": sliced,
        "meta": {
            "source": "clinical_trial_data.csv",
            "total_available": len(records),
            "returned": len(sliced),
        },
    }
