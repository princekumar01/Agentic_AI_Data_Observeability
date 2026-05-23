"""
backend/agents/supervisor.py
─────────────────────────────────────────────────────
Supervisor node — validates state, logs pipeline start,
routes to the first agent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


def supervisor_node(state: AgentState) -> AgentState:
    """
    Entry node for the LangGraph pipeline.
    Validates required state fields and logs the start of agent orchestration.
    """
    run_id = state.get("run_id", "unknown")
    logger.info(f"[Supervisor] Pipeline start | run_id={run_id}")

    if not state.get("sanitized_metrics"):
        logger.warning(f"[Supervisor] sanitized_metrics is empty for run_id={run_id}")

    if not state.get("sanitized_log_text"):
        logger.warning(f"[Supervisor] sanitized_log_text is empty for run_id={run_id}")

    # Ensure all output fields have defaults
    updated: AgentState = {
        **state,
        "data_quality_findings": state.get("data_quality_findings", ""),
        "log_analysis_findings": state.get("log_analysis_findings", ""),
        "rca_findings": state.get("rca_findings", ""),
        "recommendations": state.get("recommendations", ""),
        "compliance_review": state.get("compliance_review", ""),
        "incident_report": state.get("incident_report", ""),
        "audit_entries": state.get("audit_entries", []),
        "error": state.get("error"),
    }

    logger.info(f"[Supervisor] State validated — routing to data_quality_agent")
    return updated
