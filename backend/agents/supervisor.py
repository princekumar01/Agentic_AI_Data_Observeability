"""
supervisor.py
Supervisor agent node — deterministic routing.
Reads the Metrics JSON, assesses severity, logs a routing decision.
Does NOT call the LLM. This is a pure Python orchestration step.
"""

import json
from datetime import datetime, timezone
from backend.agents.state import AgentState


def supervisor_node(state: AgentState) -> AgentState:
    """
    Assess the Metrics JSON severity and record a routing decision
    in the audit entries list.
    """
    metrics = state["sanitized_metrics"]
    anomaly_count = metrics.get("anomaly_count", 0)
    health_score = metrics.get("overall_health_score", 100)
    anomalies = metrics.get("anomalies_detected", [])

    if health_score >= 80:
        severity_assessment = "LOW"
    elif health_score >= 60:
        severity_assessment = "MEDIUM"
    elif health_score >= 40:
        severity_assessment = "HIGH"
    else:
        severity_assessment = "CRITICAL"

    routing_summary = (
        f"Health score: {health_score}/100 | "
        f"Anomalies: {anomaly_count} | "
        f"Severity: {severity_assessment} | "
        f"Issues: {anomalies}"
    )

    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "supervisor",
        "event_type": "routing_decision",
        "stage": "supervisor",
        "data": {
            "health_score": health_score,
            "anomaly_count": anomaly_count,
            "severity_assessment": severity_assessment,
            "anomalies_detected": anomalies,
            "decision": "dispatching to data_quality → log_analysis → rca → recommendation → compliance",
            "routing_summary": routing_summary,
        },
    }

    state["audit_entries"] = state.get("audit_entries", []) + [audit_entry]
    return state
