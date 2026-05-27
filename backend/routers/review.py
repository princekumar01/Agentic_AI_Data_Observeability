"""
backend/routers/review.py
─────────────────────────────────────────────────────
Human-in-the-Loop (HITL) review endpoints.

GET  /review/pending
GET  /review/findings/{run_id}
GET  /review/token-usage/{run_id}
GET  /review/artifacts/{run_id}
POST /review/approve
POST /review/reject

On APPROVE  → audit trail updated, incident_report.md written, status = 'approved'
On REJECT   → audit trail updated, status = 'rejected'
dashboard_url returned on approval.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import (
    AgentFindings,
    ArtifactInfo,
    ArtifactsResponse,
    ApproveRequest,
    ApproveResponse,
    FindingsResponse,
    PendingRunInfo,
    PendingRunsResponse,
    RejectRequest,
    RejectResponse,
    ReviewSummary,
    TokenUsageResponse,
    AgentTokenUsage,
)
from backend.services.auth_service import require_auth_user as _require_auth
from backend.services.findings_parser_service import parse_agent_findings

router = APIRouter(prefix="/review", tags=["review"])

RUNS_DIR = os.path.join("output", "runs")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_json(path: str) -> Optional[Dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _load_config() -> Dict:
    try:
        with open("config.yaml") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def _get_run_status(run_id: str) -> str:
    from backend.routers.pipeline import get_pipeline_runs
    run = get_pipeline_runs().get(run_id)
    if run:
        return run.get("status", "unknown")
    return "unknown"


def _set_run_status(run_id: str, status_: str, review_status: str) -> None:
    from backend.routers.pipeline import get_pipeline_runs
    run = get_pipeline_runs().get(run_id)
    if run:
        run["status"] = status_
        run["review_status"] = review_status


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=PendingRunsResponse)
def pending_runs(user: Dict = Depends(_require_auth)):
    from backend.routers.pipeline import get_pipeline_runs

    pending = []
    for run in get_pipeline_runs().values():
        if run.get("status") in ("pending_review", "running"):
            config = _load_config()
            run_id = run["run_id"]
            metrics = _load_json(
                os.path.join(RUNS_DIR, run_id, "sanitized_metrics.json")
            ) or _load_json(
                os.path.join(RUNS_DIR, run_id, "rolling_metrics.json")
            ) or {}

            pending.append(PendingRunInfo(
                run_id=run_id,
                input_mode=run.get("input_mode", "csv"),
                filename=run.get("filename"),
                total_records=run.get("rows", 0),
                window_size=config.get("kafka", {}).get("window_threshold", 5),
                pipeline_status=run.get("status", "unknown"),
                started_at=run.get("started_at", ""),
                completed_at=run.get("completed_at"),
                health_score=metrics.get("health_score"),
                health_label=metrics.get("health_label"),
            ))

    return PendingRunsResponse(pending_runs=pending)


@router.get("/findings/{run_id}", response_model=FindingsResponse)
def get_findings(run_id: str, user: Dict = Depends(_require_auth)):
    output_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    # Load sanitized metrics — REQUIRED.  The findings parser joins agent
    # responses with these numbers to populate KeyFinding.affected/total/percentage.
    # rolling_metrics.json is accepted as a fallback for runs that completed
    # before the PII masking stage existed.
    metrics: Optional[Dict[str, Any]] = (
        _load_json(os.path.join(output_dir, "sanitized_metrics.json"))
        or _load_json(os.path.join(output_dir, "rolling_metrics.json"))
    )
    if metrics is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Run {run_id} is missing sanitized_metrics.json (and rolling_metrics.json). "
                "Findings cannot be produced without computed pipeline metrics."
            ),
        )

    # Load confidence scores
    conf_data: Dict[str, int] = {}
    conf_path = os.path.join(output_dir, "agent_confidence.json")
    if os.path.exists(conf_path):
        try:
            with open(conf_path) as fh:
                conf_data = json.load(fh)
        except Exception:
            pass

    responses_dir = os.path.join(output_dir, "responses")

    agent_configs = [
        ("data_quality_agent", "Data Quality Assessment"),
        ("log_analysis_agent", "Log Analysis"),
        ("rca_agent", "Root Cause Analysis"),
        ("recommendation_agent", "Recommendations"),
        ("compliance_agent", "Compliance Review"),
    ]

    agents_out: List[AgentFindings] = []
    total_completed = 0
    high_conf = 0
    low_conf = 0
    critical_issues = 0

    for agent_key, _label in agent_configs:
        resp_path = os.path.join(responses_dir, f"{agent_key}.json")
        confidence = int(conf_data.get(agent_key, 0))
        response_text = ""

        if os.path.exists(resp_path):
            try:
                with open(resp_path, encoding="utf-8") as fh:
                    resp_data = json.load(fh)
                    response_text = resp_data.get("response", "")
                    if response_text:
                        total_completed += 1
            except Exception:
                pass

        findings = parse_agent_findings(agent_key, response_text, confidence, metrics)
        agents_out.append(findings)

        if confidence >= 75:
            high_conf += 1
        else:
            low_conf += 1
        if findings.flag_for_review:
            critical_issues += 1

    overall_confidence = int(
        sum(int(conf_data.get(k, 0)) for k, _ in agent_configs)
        / max(1, len(agent_configs))
    )
    attention_required = overall_confidence < 75 or critical_issues > 0

    return FindingsResponse(
        run_id=run_id,
        agents=agents_out,
        overall_confidence=overall_confidence,
        attention_required=attention_required,
        attention_message=(
            f"{critical_issues} agent(s) flagged for review — "
            "confidence below threshold or critical issues detected"
            if attention_required else None
        ),
        review_summary=ReviewSummary(
            total_agents=len(agent_configs),
            completed=total_completed,
            high_confidence=high_conf,
            low_confidence=low_conf,
            critical_issues=critical_issues,
        ),
    )


@router.get("/token-usage/{run_id}", response_model=TokenUsageResponse)
def token_usage(run_id: str, user: Dict = Depends(_require_auth)):
    from backend.services.token_tracking_service import get_token_usage

    output_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    records = get_token_usage(run_id, output_dir)

    agents_out: List[AgentTokenUsage] = []
    total_tokens = 0
    total_cost = 0.0

    for rec in records:
        t = rec.get("total_tokens", 0)
        c = rec.get("estimated_cost_usd", 0.0)
        total_tokens += t
        total_cost += c
        agents_out.append(AgentTokenUsage(
            name=rec.get("agent_name", "unknown"),
            input_tokens=rec.get("input_tokens", 0),
            output_tokens=rec.get("output_tokens", 0),
            total_tokens=t,
            cost_usd=c,
        ))

    return TokenUsageResponse(
        run_id=run_id,
        agents=agents_out,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
    )


@router.get("/artifacts/{run_id}", response_model=ArtifactsResponse)
def list_artifacts(run_id: str, user: Dict = Depends(_require_auth)):
    output_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    artifacts: List[ArtifactInfo] = []
    for root, _dirs, files in os.walk(output_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "unknown"
            size_kb = round(os.path.getsize(fpath) / 1024, 2)
            ftype = {
                "json": "JSON Data",
                "md": "Markdown Report",
                "txt": "Text Log",
                "log": "Log File",
                "jsonl": "JSONL Stream",
                "csv": "CSV Data",
            }.get(ext, "File")
            artifacts.append(ArtifactInfo(
                name=fname,
                type=ftype,
                size_kb=size_kb,
                path=os.path.relpath(fpath, RUNS_DIR),
            ))

    return ArtifactsResponse(run_id=run_id, artifacts=artifacts)


@router.post("/approve", response_model=ApproveResponse)
def approve_run(body: ApproveRequest, user: Dict = Depends(_require_auth)):
    run_id = body.run_id
    output_dir = os.path.join(RUNS_DIR, run_id)

    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    now = datetime.now(timezone.utc).isoformat()

    # Update audit trail
    audit_path = os.path.join(output_dir, "audit_trail.json")
    if os.path.exists(audit_path):
        try:
            with open(audit_path, encoding="utf-8") as fh:
                trail = json.load(fh)
            trail["pipeline_status"] = "approved"
            trail["hitl_decision"] = {
                "decision": "approved",
                "reviewer_id": body.reviewer_id,
                "notes": body.notes,
                "decided_at": now,
                "escalated": body.escalate_to_compliance,
            }
            # Append HITL decision entry
            trail.setdefault("entries", []).append({
                "entry_id": len(trail["entries"]) + 1,
                "timestamp": now,
                "stage": "human_review",
                "event_type": "HITL_DECISION",
                "agent": None,
                "data": {
                    "decision": "approved",
                    "reviewer_id": body.reviewer_id,
                    "notes": body.notes,
                },
            })
            tmp = audit_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(trail, fh, indent=2)
            os.replace(tmp, audit_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not update audit trail: {exc}")

    # Write final incident_report.md ONLY on approval
    draft_path = os.path.join(output_dir, "incident_report_draft.md")
    report_path = os.path.join(output_dir, "incident_report.md")
    if os.path.exists(draft_path):
        with open(draft_path, encoding="utf-8") as fh:
            draft_content = fh.read()
        final_content = draft_content.replace(
            "**Status:** Pending Human Review",
            f"**Status:** APPROVED\n**Approved By:** {body.reviewer_id}\n**Approved At:** {now}",
        )
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(final_content)

    # Write approval_record.json
    approval_record = {
        "run_id": run_id,
        "decision": "approved",
        "reviewer_id": body.reviewer_id,
        "notes": body.notes,
        "decided_at": now,
        "escalated": body.escalate_to_compliance,
    }
    with open(os.path.join(output_dir, "approval_record.json"), "w") as fh:
        json.dump(approval_record, fh, indent=2)

    # Update in-memory pipeline state
    _set_run_status(run_id, "approved", "approved")

    from backend.services.alert_service import write_alert
    write_alert(
        severity="INFO",
        message=f"Run {run_id} approved by {body.reviewer_id}",
        run_id=run_id,
        source="review_service",
        title="Pipeline Approved",
    )

    return ApproveResponse(
        success=True,
        run_id=run_id,
        status="approved",
        approved_by=body.reviewer_id,
        approved_at=now,
        dashboard_url=f"/dashboard?run_id={run_id}",
    )


@router.post("/reject", response_model=RejectResponse)
def reject_run(body: RejectRequest, user: Dict = Depends(_require_auth)):
    run_id = body.run_id
    output_dir = os.path.join(RUNS_DIR, run_id)

    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    now = datetime.now(timezone.utc).isoformat()

    # Update audit trail
    audit_path = os.path.join(output_dir, "audit_trail.json")
    if os.path.exists(audit_path):
        try:
            with open(audit_path, encoding="utf-8") as fh:
                trail = json.load(fh)
            trail["pipeline_status"] = "rejected"
            trail["hitl_decision"] = {
                "decision": "rejected",
                "reviewer_id": body.reviewer_id,
                "notes": body.reason,
                "decided_at": now,
                "escalated": body.escalate_to_compliance,
            }
            trail.setdefault("entries", []).append({
                "entry_id": len(trail["entries"]) + 1,
                "timestamp": now,
                "stage": "human_review",
                "event_type": "HITL_DECISION",
                "agent": None,
                "data": {
                    "decision": "rejected",
                    "reviewer_id": body.reviewer_id,
                    "reason": body.reason,
                },
            })
            tmp = audit_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(trail, fh, indent=2)
            os.replace(tmp, audit_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not update audit trail: {exc}")

    # Write rejection record
    rejection_record = {
        "run_id": run_id,
        "decision": "rejected",
        "reviewer_id": body.reviewer_id,
        "reason": body.reason,
        "decided_at": now,
        "escalated": body.escalate_to_compliance,
    }
    with open(os.path.join(output_dir, "rejection_record.json"), "w") as fh:
        json.dump(rejection_record, fh, indent=2)

    # Update in-memory pipeline state
    _set_run_status(run_id, "rejected", "rejected")

    from backend.services.alert_service import write_alert
    write_alert(
        severity="WARNING",
        message=f"Run {run_id} rejected by {body.reviewer_id}: {body.reason or 'No reason given'}",
        run_id=run_id,
        source="review_service",
        title="Pipeline Rejected",
    )

    return RejectResponse(
        success=True,
        run_id=run_id,
        status="rejected",
        rejected_by=body.reviewer_id,
        rejected_at=now,
    )
