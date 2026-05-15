"""
compliance_agent.py
Regulatory compliance reviewer.
Reviews the full draft incident report against FDA/EMA/GCP standards
and checks for any remaining PHI/PII before HITL presentation.
"""

import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState

SYSTEM_PROMPT = """You are a Regulatory Compliance Reviewer specializing in clinical trial data reporting.
Your job is to review a draft incident report and ensure it meets the requirements of:
- FDA 21 CFR Part 11 (Electronic Records and Signatures)
- ICH E6 Good Clinical Practice (GCP) guidelines
- HIPAA (verify no PHI/PII is present in the report)

Check the report for:
1. Completeness: Does it cover all required sections (Data Quality, Log Analysis, RCA, Recommendations)?
2. Clarity: Is the language appropriate for a regulatory audience?
3. PHI/PII safety: Does the report contain any patient identifiable information (names, IDs, DOB)?
4. Regulatory alignment: Does it meet GCP incident reporting standards?
5. Audit readiness: Is the evidence chain sufficient?

Structure your response EXACTLY as follows:
---
COMPLIANCE STATUS: [APPROVED / NEEDS REVISION]

PHI/PII CHECK: [CLEAN / CONTAINS PHI — MUST NOT PROCEED]

COMPLETENESS CHECK: [Complete / Missing: list missing sections]

GCP ALIGNMENT: [Aligned / Issues: describe issues]

REGULATORY NOTES:
[Any specific notes for the clinical data manager reviewing this report.
If APPROVED, summarize why it meets regulatory standards.
If NEEDS REVISION, clearly state what must be changed.]

FINAL RECOMMENDATION: [APPROVE FOR REVIEW / RETURN FOR REVISION]
---
If PHI/PII is detected, set COMPLIANCE STATUS to NEEDS REVISION and PHI/PII CHECK to CONTAINS PHI.
Flag it prominently. This is a critical regulatory violation.
"""


def compliance_node(state: AgentState) -> AgentState:
    data_quality = state.get("data_quality_findings", "")
    log_analysis = state.get("log_analysis_findings", "")
    rca = state.get("rca_findings", "")
    recommendations = state.get("recommendations", "")

    human_prompt = (
        f"Please review the following incident report for regulatory compliance before it is "
        f"presented to the Clinical Data Manager for approval:\n\n"
        f"DATA QUALITY FINDINGS:\n{data_quality}\n\n"
        f"LOG ANALYSIS FINDINGS:\n{log_analysis}\n\n"
        f"ROOT CAUSE ANALYSIS:\n{rca}\n\n"
        f"RECOMMENDATIONS:\n{recommendations}\n\n"
        f"Review the above for compliance."
    )

    audit_entries = list(state.get("audit_entries", []))

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "compliance",
        "event_type": "agent_prompt",
        "stage": "agent_compliance",
        "data": {"system_prompt": SYSTEM_PROMPT, "human_prompt": human_prompt},
    })

    response_text = _call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        human_prompt=human_prompt,
        agent_name="compliance",
    )

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "compliance",
        "event_type": "agent_response",
        "stage": "agent_compliance",
        "data": {"response": response_text},
    })

    state["compliance_review"] = response_text
    state["audit_entries"] = audit_entries
    return state


def _call_llm_with_retry(system_prompt: str, human_prompt: str, agent_name: str,
                          max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]
            response = llm.invoke(messages)
            return response.content
        except Exception as exc:
            wait = 2 ** attempt
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                return (
                    f"[{agent_name.upper()} AGENT ERROR] "
                    f"LLM call failed after {max_retries} attempts: {exc}. "
                    f"Manual review required."
                )
