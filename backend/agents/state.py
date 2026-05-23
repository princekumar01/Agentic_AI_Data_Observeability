"""
backend/agents/state.py
─────────────────────────────────────────────────────
AgentState TypedDict shared across all LangGraph nodes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    run_id: str
    sanitized_metrics: Dict[str, Any]
    sanitized_log_text: str
    streaming_metadata: Dict[str, Any]
    output_dir: str

    # Agent outputs (populated as pipeline progresses)
    data_quality_findings: str
    log_analysis_findings: str
    rca_findings: str
    recommendations: str
    compliance_review: str
    incident_report: str

    # Audit and tracking
    audit_entries: List[Dict[str, Any]]
    error: Optional[str]
