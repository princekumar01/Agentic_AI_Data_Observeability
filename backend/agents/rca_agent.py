"""
rca_agent.py
Root Cause Analysis agent.
Receives both Data Quality AND Log Analysis outputs simultaneously
and cross-correlates them to identify root causes.
"""

import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState

SYSTEM_PROMPT = """You are a Root Cause Analysis (RCA) Specialist for clinical trial data pipelines.
You receive two inputs: a data quality assessment and an operational log analysis.
Your job is to cross-correlate the findings from both and identify the root cause of any incidents.

For example: if the Data Quality report shows a 20% volume drop AND the Log Analysis report
shows a "Database timeout connecting to EU database" at a specific timestamp — the root cause
is the database connectivity failure, not a data issue.

Structure your response EXACTLY as follows:
---
INCIDENT DETECTED: [Yes / No]
INCIDENT SEVERITY: [Low / Medium / High / Critical / N/A]

ROOT CAUSE:
[Describe the root cause clearly. Cite which metric triggered the anomaly and which log event
corroborated it. Include timestamps where available. Format: "Anomaly X in metric Y was caused
by event Z in log at timestamp T." If no incident, write "No incident — pipeline ran normally."]

CONTRIBUTING FACTORS:
- [Factor 1]
- [Factor 2]
(write "None" if no incident)

IMPACT ASSESSMENT:
[What is the potential impact on the clinical trial data integrity?
If no incident, write "No impact — data integrity maintained."]
---
Base your analysis entirely on the two inputs provided. Do not speculate beyond what the data shows.
"""


def rca_node(state: AgentState) -> AgentState:
    data_quality_findings = state.get("data_quality_findings", "")
    log_analysis_findings = state.get("log_analysis_findings", "")

    human_prompt = (
        f"DATA QUALITY ASSESSMENT:\n{data_quality_findings}\n\n"
        f"LOG ANALYSIS ASSESSMENT:\n{log_analysis_findings}\n\n"
        f"Based on both inputs above, perform a root cause analysis."
    )

    audit_entries = list(state.get("audit_entries", []))

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "rca",
        "event_type": "agent_prompt",
        "stage": "agent_rca",
        "data": {"system_prompt": SYSTEM_PROMPT, "human_prompt": human_prompt},
    })

    response_text = _call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        human_prompt=human_prompt,
        agent_name="rca",
    )

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "rca",
        "event_type": "agent_response",
        "stage": "agent_rca",
        "data": {"response": response_text},
    })

    state["rca_findings"] = response_text
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
