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
from fastapi import APIRouter, Depends, Header, HTTPException

from backend.models.schemas import (
    AgentFindings,
    ArtifactInfo,
    ArtifactsResponse,
    ApproveRequest,
    ApproveResponse,
    FindingsResponse,
    KeyFinding,
    PendingRunInfo,
    PendingRunsResponse,
    RejectRequest,
    RejectResponse,
    ReviewSummary,
    TokenUsageResponse,
    AgentTokenUsage,
)
from backend.services import auth_service

router = APIRouter(prefix="/review", tags=["review"])

RUNS_DIR = os.path.join("output", "runs")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _require_auth(authorization: Optional[str] = Header(default=None)) -> Dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return auth_service.get_current_user(authorization[7:])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


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


def _parse_agent_findings(
    agent_name: str,
    response_text: str,
    confidence: int,
) -> AgentFindings:
    """
    Parse agent response text into structured AgentFindings.
    Extracts key findings as list items from the response.
    """
    import re

    lines = [l.strip() for l in response_text.split("\n") if l.strip()]
    summary = ""
    key_findings: List[KeyFinding] = []
    evidence = ""
    recommendations = ""
    insight = ""

    # Extract SUMMARY section
    in_summary = False
    for line in lines:
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
            in_summary = True
        elif in_summary and not any(line.startswith(h) for h in [
            "PILLAR:", "STATUS:", "FINDING:", "OVERALL SEVERITY:", "CONFIDENCE:",
            "ERROR COUNT:", "WARNING COUNT:", "ROOT CAUSE", "INCIDENT:", "PRIORITY:",
            "COMPLIANCE STATUS:", "PHI/PII CHECK:",
        ]):
            if summary and line:
                summary += " " + line
            in_summary = False

    # Extract findings as key findings
    finding_count = 0
    for line in lines:
        if line.startswith("FINDING:") and finding_count < 5:
            finding_text = line.replace("FINDING:", "").strip()
            # Try to extract a percentage or count
            pct_match = re.search(r"([\d.]+)\s*%", finding_text)
            count_match = re.search(r"\b(\d+)\b", finding_text)
            pct = float(pct_match.group(1)) if pct_match else 0.0
            count = int(count_match.group(1)) if count_match else 0
            # Extract severity
            sev_match = re.search(r"\b(Critical|High|Medium|Low|PASS|WARN|FAIL)\b", finding_text, re.I)
            sev = sev_match.group(1).capitalize() if sev_match else "Medium"
            key_findings.append(KeyFinding(
                issue=finding_text[:80],
                severity=sev,
                affected=count,
                total=500,
                percentage=pct,
                trend="stable",
            ))
            finding_count += 1

    # Evidence from EVIDENCE: lines
    for line in lines:
        if line.startswith("EVIDENCE:"):
            evidence = line.replace("EVIDENCE:", "").strip()

    # Recommendations from ACTION: lines
    rec_parts = []
    for line in lines:
        if line.startswith("ACTION:"):
            rec_parts.append(line.replace("ACTION:", "").strip())
    recommendations = "; ".join(rec_parts[:2]) if rec_parts else ""

    # Insight from FINAL RECOMMENDATION / OPERATIONAL STATUS
    for line in lines:
        if line.startswith("FINAL RECOMMENDATION:") or line.startswith("OPERATIONAL STATUS:"):
            insight = line.split(":", 1)[-1].strip()
            break

    # Flag for review if confidence < 75 or critical found
    flag = confidence < 75 or any(kf.severity == "Critical" for kf in key_findings)

    return AgentFindings(
        name=agent_name,
        status="COMPLETED",
        confidence=confidence,
        confidence_label=_conf_label(confidence),
        flag_for_review=flag,
        summary=summary or response_text[:200],
        key_findings=key_findings[:5],
        evidence=evidence,
        recommendations=recommendations,
        insight=insight,
    )


def _conf_label(c: int) -> str:
    if c >= 90:
        return "Very High"
    elif c >= 75:
        return "High"
    elif c >= 60:
        return "Medium"
    else:
        return "Low"


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
                window_size=config.get("kafka", {}).get("window_threshold", 500),
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

    # Load confidence scores
    conf_data: Dict[str, int] = {}
    conf_path = os.path.join(output_dir, "agent_confidence.json")
    if os.path.exists(conf_path):
        try:
            with open(conf_path) as fh:
                conf_data = json.load(fh)
        except Exception:
            pass

    # Load responses
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
        confidence = conf_data.get(agent_key, 0)
        response_text = ""

        if os.path.exists(resp_path):
            try:
                with open(resp_path) as fh:
                    resp_data = json.load(fh)
                    response_text = resp_data.get("response", "")
                    total_completed += 1
            except Exception:
                pass

        findings = _parse_agent_findings(agent_key, response_text, confidence)
        agents_out.append(findings)

        if confidence >= 75:
            high_conf += 1
        else:
            low_conf += 1
        if findings.flag_for_review:
            critical_issues += 1

    overall_confidence = int(
        sum(conf_data.get(k, 0) for k, _ in agent_configs) / max(1, len(agent_configs))
    )
    attention_required = overall_confidence < 75 or critical_issues > 0

    return FindingsResponse(
        run_id=run_id,
        agents=agents_out,
        overall_confidence=overall_confidence,
        attention_required=attention_required,
        attention_message=(
            f"{critical_issues} agent(s) flagged for review — confidence below threshold or critical issues detected"
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
