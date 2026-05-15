"""
schemas.py
All Pydantic request/response models used across the FastAPI backend.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class RunTriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


class PipelineStatus(BaseModel):
    run_id: str
    status: str
    current_stage: str
    progress_pct: int
    errors: List[str]
    warnings: List[str]


class RunHistoryItem(BaseModel):
    run_id: str
    started_at: str
    status: str


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    passed: bool
    errors: List[str]
    warnings: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# HITL Review
# ─────────────────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    run_id: str
    reviewer_id: str
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    run_id: str
    decision: str
    message: str


class ReviewPayload(BaseModel):
    run_id: str
    incident_report_md: str
    compliance_status: str
    compliance_notes: str
    metrics_summary: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class DashboardData(BaseModel):
    run_id: str
    health_score: int
    metrics: Dict[str, Any]
    agent_findings: Dict[str, str]
    incident_report_md: str
    audit_summary: Dict[str, Any]
    pillar_chart_data: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    entry_id: int
    timestamp: str
    stage: str
    event_type: str
    agent: Optional[str] = None
    data: Dict[str, Any]
