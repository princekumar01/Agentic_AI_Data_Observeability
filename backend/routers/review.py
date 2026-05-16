"""
review.py
FastAPI router for Human-in-the-Loop review endpoints.

GET  /review/{run_id}    — fetch the draft incident report for review
POST /review/approve     — approve the report
POST /review/reject      — reject the report (requires notes)
"""

import os
import json

import yaml
from fastapi import APIRouter, HTTPException

from backend.models.schemas import ReviewRequest, ReviewResponse, ReviewPayload
from backend.services.audit_service import AuditService, load_audit

router = APIRouter()


def _load_config() -> dict:
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def _get_run_dir(run_id: str, runs_dir: str) -> str:
    run_dir = os.path.join(runs_dir, run_id)
    if not os.path.isdir(run_dir):
        raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found.")
    return run_dir


def _load_json_file(run_dir: str, filename: str) -> dict:
    path = os.path.join(run_dir, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_text_file(run_dir: str, filename: str) -> str:
    path = os.path.join(run_dir, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{run_id}", response_model=ReviewPayload)
async def get_review_payload(run_id: str):
    """
    Return the incident report draft + metrics summary for the HITL review page.
    Only available when pipeline_status is 'pending_review'.
    """
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]
    run_dir = _get_run_dir(run_id, runs_dir)

    audit = load_audit(run_id, runs_dir)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit trail not found for this run.")

    status = audit.get("pipeline_status", "unknown")
    if status not in ("pending_review", "approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Run '{run_id}' is not ready for review. Current status: '{status}'.",
        )

    # Load draft report
    incident_report_md = _load_text_file(run_dir, "incident_report_draft.md")
    if not incident_report_md:
        raise HTTPException(
            status_code=404,
            detail="Incident report draft not found. Pipeline may not have completed.",
        )

    # Load metrics for summary card
    metrics = _load_json_file(run_dir, "sanitized_metrics.json")
    if not metrics:
        metrics = _load_json_file(run_dir, "metrics.json")

    # Extract compliance status from audit
    compliance_status = "UNKNOWN"
    compliance_notes = ""
    for entry in audit.get("entries", []):
        if entry.get("agent") == "compliance" and entry.get("event_type") == "agent_response":
            response = entry.get("data", {}).get("response", "")
            for line in response.splitlines():
                if "COMPLIANCE STATUS:" in line:
                    compliance_status = line.split("COMPLIANCE STATUS:")[-1].strip()
                if "REGULATORY NOTES:" in line:
                    # Grab following lines as notes
                    pass
            compliance_notes = response
            break

    metrics_summary = {
        "health_score": metrics.get("overall_health_score", 0),
        "anomaly_count": metrics.get("anomaly_count", 0),
        "anomalies_detected": metrics.get("anomalies_detected", []),
        "pillar_statuses": {
            "freshness": metrics.get("pillar_freshness", {}).get("freshness_ok", True),
            "volume": not metrics.get("pillar_volume", {}).get("volume_anomaly", False),
            "schema": (
                len(metrics.get("pillar_schema", {}).get("missing_columns", [])) == 0
                and all(
                    check.get("passed", False)
                    for check in metrics.get("pillar_schema", {}).get("dtype_checks", {}).values()
                )
                and metrics.get("pillar_schema", {}).get("duplicate_patient_ids", 0) == 0
            ),
            "distribution": True,
            "lineage": metrics.get("pillar_lineage", {}).get("error_count", 0) == 0,
        },
    }

    return ReviewPayload(
        run_id=run_id,
        incident_report_md=incident_report_md,
        compliance_status=compliance_status,
        compliance_notes=compliance_notes,
        metrics_summary=metrics_summary,
    )


@router.post("/approve", response_model=ReviewResponse)
async def approve_report(request: ReviewRequest):
    """
    Approve the incident report. Requires reviewer_id.
    Writes incident_report.md and updates audit trail.
    """
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]
    run_dir = _get_run_dir(request.run_id, runs_dir)

    audit = load_audit(request.run_id, runs_dir)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit trail not found.")

    if audit.get("pipeline_status") != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not in 'pending_review' state. "
                   f"Current status: '{audit.get('pipeline_status')}'.",
        )

    if not request.reviewer_id or not request.reviewer_id.strip():
        raise HTTPException(status_code=400, detail="reviewer_id is required for approval.")

    # Copy draft to final incident_report.md
    draft_path = os.path.join(run_dir, "incident_report_draft.md")
    final_path = os.path.join(run_dir, "incident_report.md")
    if os.path.exists(draft_path):
        with open(draft_path, "r", encoding="utf-8") as f:
            draft_content = f.read()
        approved_content = (
            draft_content
            + f"\n\n---\n\n"
            f"**APPROVED BY:** {request.reviewer_id}  \n"
            f"**APPROVED AT:** {_now()}  \n"
            f"**REVIEWER NOTES:** {request.notes or 'None'}  \n"
        )
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(approved_content)

    # Record HITL decision in audit trail
    audit_svc = _reload_audit_service(request.run_id, run_dir, audit)
    audit_svc.record_hitl_decision(
        decision="approved",
        reviewer_id=request.reviewer_id,
        notes=request.notes or "",
    )

    # Update in-memory progress (import here to avoid circular import)
    try:
        from backend.routers.pipeline import _update_progress
        _update_progress(request.run_id, "approved", "approved", 100)
    except Exception:
        pass

    return ReviewResponse(
        run_id=request.run_id,
        decision="approved",
        message=f"Report approved by {request.reviewer_id}. Dashboard is now unlocked.",
    )


@router.post("/reject", response_model=ReviewResponse)
async def reject_report(request: ReviewRequest):
    """
    Reject the incident report. Notes are required for rejection.
    """
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]
    run_dir = _get_run_dir(request.run_id, runs_dir)

    audit = load_audit(request.run_id, runs_dir)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit trail not found.")

    if audit.get("pipeline_status") != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not in 'pending_review' state.",
        )

    if not request.notes or not request.notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Notes are required when rejecting a report. "
                   "Please describe what needs to be revised.",
        )

    audit_svc = _reload_audit_service(request.run_id, run_dir, audit)
    audit_svc.record_hitl_decision(
        decision="rejected",
        reviewer_id=request.reviewer_id or "anonymous",
        notes=request.notes,
    )

    try:
        from backend.routers.pipeline import _update_progress
        _update_progress(request.run_id, "rejected", "rejected", 95)
    except Exception:
        pass

    return ReviewResponse(
        run_id=request.run_id,
        decision="rejected",
        message="Report rejected. Please re-run the pipeline after investigating the issues.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _reload_audit_service(run_id: str, run_dir: str, existing_audit: dict) -> AuditService:
    """
    Re-attach an AuditService to an existing audit file.
    We set the entry counter to the current count so IDs continue correctly.
    """
    svc = object.__new__(AuditService)
    svc.run_id = run_id
    svc.audit_path = os.path.join(run_dir, "audit_trail.json")
    svc.entry_counter = len(existing_audit.get("entries", []))
    return svc


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
