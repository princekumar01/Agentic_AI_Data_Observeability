"""
recommendation_agent.py
Generates actionable remediation recommendations with citations
from the RCA findings.
"""

import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState

SYSTEM_PROMPT = """You are a Clinical Data Pipeline Remediation Specialist.
You receive a root cause analysis of a clinical trial data pipeline incident.
Your job is to generate highly specific, actionable remediation recommendations.

For EACH anomaly detected in this pipeline, you must propose a remediation plan structured exactly as follows:

ANOMALY: [Name of anomaly, e.g., high_nulls_side_effect or glucose_level_outliers]
- Immediate Action: [what to do today, e.g. quarantine rows]
- Investigation Step: [what to query/check, e.g. cross-tabulate by site]
- Process Change: [what to fix upstream so it doesn't recur, e.g. update EDC form validation]
- Responsible Team: [Data Engineering / Clinical Operations / IT / QA]

Structure your response EXACTLY with the headers above for each anomaly.
Be highly specific and technically accurate. Use the exact counts and names from the findings.
"""


def recommendation_node(state: AgentState) -> AgentState:
    rca_findings = state.get("rca_findings", "")
    data_quality_findings = state.get("data_quality_findings", "")
    metrics = state.get("sanitized_metrics", {})
    anomalies = metrics.get("anomalies_detected", [])

    human_prompt = (
        f"ANOMALIES DETECTED:\n{anomalies}\n\n"
        f"ROOT CAUSE ANALYSIS:\n{rca_findings}\n\n"
        f"DATA QUALITY SUMMARY:\n{data_quality_findings}\n\n"
        f"Generate remediation recommendations for each anomaly."
    )

    audit_entries = list(state.get("audit_entries", []))

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "recommendation",
        "event_type": "agent_prompt",
        "stage": "agent_recommendation",
        "data": {"system_prompt": SYSTEM_PROMPT, "human_prompt": human_prompt},
    })

    response_text = _call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        human_prompt=human_prompt,
        agent_name="recommendation",
    )

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "recommendation",
        "event_type": "agent_response",
        "stage": "agent_recommendation",
        "data": {"response": response_text},
    })

    state["recommendations"] = response_text
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
