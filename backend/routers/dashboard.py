"""
dashboard.py
FastAPI router for the clinical analytics dashboard endpoint.

GET /dashboard/{run_id} — returns all data needed for the Streamlit dashboard
"""

import yaml
from fastapi import APIRouter, HTTPException

from backend.services.dashboard_service import load_dashboard_data
from backend.services.audit_service import load_audit

router = APIRouter()


def _load_config() -> dict:
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


@router.get("/{run_id}")
async def get_dashboard(run_id: str):
    """
    Return all artifacts for a completed, approved run.
    Only accessible when pipeline_status == 'approved'.
    """
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]

    # Gate: only approved runs can access the dashboard
    audit = load_audit(run_id, runs_dir)
    if not audit:
        raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found.")

    status = audit.get("pipeline_status", "unknown")
    if status != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"Dashboard is locked. Run status is '{status}'. "
                   f"Dashboard only available after human approval.",
        )

    data = load_dashboard_data(run_id, runs_dir)
    if not data:
        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard data. Some artifacts may be missing.",
        )

    return data
