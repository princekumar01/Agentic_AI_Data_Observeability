"""
state.py
Defines the shared AgentState TypedDict passed between all LangGraph nodes.
Every agent reads from and writes to this state object.
"""

from typing import TypedDict, Optional


class AgentState(TypedDict):
    run_id: str
    sanitized_metrics: dict          # Sanitized Metrics JSON from PII layer
    sanitized_log_text: str          # Content of sanitized_log.txt
    data_quality_findings: str       # Output of Data Quality Agent
    log_analysis_findings: str       # Output of Log Analysis Agent
    rca_findings: str                # Output of RCA Agent
    recommendations: str             # Output of Recommendation Agent
    compliance_review: str           # Output of Compliance Agent
    incident_report: str             # Final assembled incident report (markdown)
    audit_entries: list              # Audit entries accumulated during agent calls
    error: Optional[str]             # Set if any node encounters a fatal error
