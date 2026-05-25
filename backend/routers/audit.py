"""
backend/routers/audit.py
─────────────────────────────────────────────────────
GET /audit/summary
GET /audit/events
GET /audit/events/{event_id}
GET /audit/events/{event_id}/prompt

Reads from output/runs/*/audit_trail.json files.
Immutable — no write endpoints.
"""
from __future__ import annotations

import json
import os
import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from backend.models.schemas import (
    AgentInfo,
    AuditEventDetailResponse,
    AuditEventItem,
    AuditEventsResponse,
    AuditPromptResponse,
    AuditSummaryResponse,
    EventDetailInfo,
    EventMetadata,
    RequestResponseInfo,
    TokenUsageDetail,
)
from backend.services import auth_service

router = APIRouter(prefix="/audit", tags=["audit"])

RUNS_DIR = os.path.join("output", "runs")


def _require_auth(authorization: Optional[str] = Header(default=None)) -> Dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return auth_service.get_current_user(authorization[7:])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _load_all_audit_entries() -> List[Dict[str, Any]]:
    """
    Walk output/runs/*/audit_trail.json and collect all entries.
    Returns flat list sorted by timestamp descending.
    """
    all_entries: List[Dict] = []
    if not os.path.isdir(RUNS_DIR):
        return all_entries

    for run_dir in os.listdir(RUNS_DIR):
        trail_path = os.path.join(RUNS_DIR, run_dir, "audit_trail.json")
        if not os.path.exists(trail_path):
            continue
        try:
            with open(trail_path, encoding="utf-8") as fh:
                trail = json.load(fh)
        except Exception:
            continue

        run_id = trail.get("run_id", run_dir)
        for entry in trail.get("entries", []):
            # Enrich each entry with run_id
            enriched = dict(entry)
            enriched["run_id"] = run_id
            all_entries.append(enriched)

    all_entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return all_entries


def _event_type_color(event_type: str) -> str:
    mapping = {
        "STAGE_START": "blue",
        "STAGE_COMPLETE": "green",
        "HITL_DECISION": "purple",
        "PII_MASKING_COMPLETE": "orange",
        "AGENT_RUN": "teal",
        "ERROR": "red",
        "WARNING": "yellow",
    }
    return mapping.get(event_type, "gray")


def _entry_to_item(entry: Dict) -> AuditEventItem:
    stage = entry.get("stage", "pipeline")
    event_type = entry.get("event_type", "UNKNOWN")
    data = entry.get("data", {})
    run_id = entry.get("run_id")
    agent = entry.get("agent")

    # Build a human-readable description
    if event_type == "STAGE_START":
        description = f"Stage '{stage}' started"
        detail = json.dumps(data)[:120]
    elif event_type == "STAGE_COMPLETE":
        description = f"Stage '{stage}' completed"
        detail = json.dumps(data)[:120]
    elif event_type == "HITL_DECISION":
        decision = data.get("decision", "unknown")
        reviewer = data.get("reviewer_id", "unknown")
        description = f"HITL Decision: {decision} by {reviewer}"
        detail = data.get("notes", "") or ""
    elif agent:
        description = f"Agent '{agent}' executed"
        detail = json.dumps(data)[:120]
    else:
        description = event_type.replace("_", " ").title()
        detail = json.dumps(data)[:120]

    return AuditEventItem(
        id=str(entry.get("entry_id", "?")),
        time=entry.get("timestamp", ""),
        event_type=event_type,
        event_type_color=_event_type_color(event_type),
        agent_source=agent or stage or "pipeline",
        description=description,
        detail=detail,
        user=data.get("reviewer_id", "system"),
        status="success" if "COMPLETE" in event_type or "DECISION" in event_type else "info",
        run_id=run_id,
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=AuditSummaryResponse)
def audit_summary(user: Dict = Depends(_require_auth)):
    all_entries = _load_all_audit_entries()

    total = len(all_entries)
    ai_executions = sum(1 for e in all_entries if e.get("agent"))
    data_access = sum(1 for e in all_entries if e.get("stage") in ("input_discovery", "preprocessing"))
    hitl = sum(1 for e in all_entries if e.get("event_type") == "HITL_DECISION")
    errors = sum(1 for e in all_entries if e.get("event_type") == "ERROR")

    return AuditSummaryResponse(
        period={"start": None, "end": None},
        total_events=total,
        total_events_change_pct=0.0,
        ai_agent_executions=ai_executions,
        ai_executions_change_pct=0.0,
        data_access_events=data_access,
        data_access_change_pct=0.0,
        user_actions=hitl,
        user_actions_change_pct=0.0,
        errors=errors,
        errors_change_pct=0.0,
    )


@router.get("/events", response_model=AuditEventsResponse)
def list_audit_events(
    run_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    agent: Optional[str] = Query(default=None),
    stage: Optional[str] = Query(default=None),
    user_filter: Optional[str] = Query(default=None, alias="user"),
    from_dt: Optional[str] = Query(default=None),
    to_dt: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    user: Dict = Depends(_require_auth),
):
    all_entries = _load_all_audit_entries()

    # Filter
    filtered: List[Dict] = []
    for entry in all_entries:
        if run_id and entry.get("run_id") != run_id:
            continue
        if event_type and entry.get("event_type") != event_type:
            continue
        if agent and entry.get("agent") != agent:
            continue
        if stage and entry.get("stage") != stage:
            continue
        if user_filter:
            data = entry.get("data", {})
            entry_user = data.get("reviewer_id", "system")
            if entry_user != user_filter:
                continue
        if from_dt and entry.get("timestamp", "") < from_dt:
            continue
        if to_dt and entry.get("timestamp", "") > to_dt:
            continue
        filtered.append(entry)

    total = len(filtered)
    start = (page - 1) * limit
    page_entries = filtered[start : start + limit]

    return AuditEventsResponse(
        total=total,
        page=page,
        limit=limit,
        events=[_entry_to_item(e) for e in page_entries],
    )


@router.get("/events/{event_id}", response_model=AuditEventDetailResponse)
def get_audit_event(event_id: str, user: Dict = Depends(_require_auth)):
    all_entries = _load_all_audit_entries()

    entry: Optional[Dict] = None
    for e in all_entries:
        if str(e.get("entry_id", "")) == event_id:
            entry = e
            break

    if not entry:
        raise HTTPException(status_code=404, detail="Audit event not found")

    run_id = entry.get("run_id")
    agent_name = entry.get("agent", "pipeline")
    stage = entry.get("stage", "pipeline")
    data = entry.get("data", {})
    event_type = entry.get("event_type", "UNKNOWN")

    # Try to load token usage for this agent/run
    token_usage = TokenUsageDetail(
        input_tokens=0, output_tokens=0, total_tokens=0, estimated_cost_usd=0.0
    )
    if run_id and agent_name:
        token_path = os.path.join(RUNS_DIR, run_id, "token_usage.json")
        if os.path.exists(token_path):
            try:
                with open(token_path) as fh:
                    records = json.load(fh)
                for rec in records:
                    if rec.get("agent_name") == agent_name:
                        token_usage = TokenUsageDetail(
                            input_tokens=rec.get("input_tokens", 0),
                            output_tokens=rec.get("output_tokens", 0),
                            total_tokens=rec.get("total_tokens", 0),
                            estimated_cost_usd=rec.get("estimated_cost_usd", 0.0),
                        )
                        break
            except Exception:
                pass

    # Build response
    return AuditEventDetailResponse(
        id=event_id,
        event_type=event_type,
        status="success" if "COMPLETE" in event_type else "info",
        time=entry.get("timestamp", ""),
        run_id=run_id,
        agent=AgentInfo(
            name=agent_name,
            model="gpt-4o" if agent_name != "compliance_agent" else "gpt-4o-mini",
            version="1.0",
        ),
        token_usage=token_usage,
        event_details=EventDetailInfo(
            description=f"Stage '{stage}' — {event_type}",
            task=stage,
            status="completed",
            duration_seconds=data.get("duration_ms", 0) / 1000 if data.get("duration_ms") else 0.0,
        ),
        request_response=RequestResponseInfo(
            prompt_path=(
                os.path.join(RUNS_DIR, run_id, "prompts", f"{agent_name}.txt")
                if run_id and agent_name and os.path.exists(
                    os.path.join(RUNS_DIR, run_id, "prompts", f"{agent_name}.txt")
                )
                else None
            ),
            response_path=(
                os.path.join(RUNS_DIR, run_id, "responses", f"{agent_name}.json")
                if run_id and agent_name and os.path.exists(
                    os.path.join(RUNS_DIR, run_id, "responses", f"{agent_name}.json")
                )
                else None
            ),
        ),
        metadata=EventMetadata(
            source_ip="127.0.0.1",
            environment="local",
            platform="Clinical Observability v6.0",
            session_id=run_id or "N/A",
            user=data.get("reviewer_id", "system"),
        ),
    )


@router.get("/events/{event_id}/prompt", response_model=AuditPromptResponse)
def get_audit_event_prompt(event_id: str, user: Dict = Depends(_require_auth)):
    all_entries = _load_all_audit_entries()

    entry: Optional[Dict] = None
    for e in all_entries:
        if str(e.get("entry_id", "")) == event_id:
            entry = e
            break

    if not entry:
        raise HTTPException(status_code=404, detail="Audit event not found")

    run_id = entry.get("run_id")
    agent_name = entry.get("agent")

    if not run_id or not agent_name:
        raise HTTPException(status_code=404, detail="No prompt available for this event")

    prompt_path = os.path.join(RUNS_DIR, run_id, "prompts", f"{agent_name}.txt")
    if not os.path.exists(prompt_path):
        raise HTTPException(status_code=404, detail="Prompt file not found")

    with open(prompt_path, encoding="utf-8") as fh:
        prompt_text = fh.read()

    return AuditPromptResponse(event_id=event_id, prompt=prompt_text)


@router.get("/export")
def export_audit_events(
    format: str = Query("csv", pattern="^(csv|json)$"),
    user: Dict = Depends(_require_auth),
):
    events = [_entry_to_item(e).model_dump() for e in _load_all_audit_entries()]

    if format == "json":
        return Response(
            content=json.dumps(events, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_log.json"},
        )

    buffer = io.StringIO()
    fieldnames = [
        "id", "time", "event_type", "event_type_color", "agent_source",
        "description", "detail", "user", "status", "run_id",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(events)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
