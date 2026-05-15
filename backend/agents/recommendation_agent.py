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
Your job is to generate clear, actionable remediation recommendations.

Each recommendation must:
1. Reference the specific anomaly or root cause it addresses
2. Specify the responsible team (Data Engineering / Clinical Operations / IT / QA)
3. Specify priority: Immediate (same day) / Short-term (within 1 week) / Long-term (within 1 month)
4. Be specific and technically accurate

Structure your response EXACTLY as follows:
---
RECOMMENDATION 1:
PRIORITY: [Immediate / Short-term / Long-term]
RESPONSIBLE TEAM: [team name]
ACTION: [Specific action to take]
RATIONALE: [Why this addresses the root cause — cite the specific finding]

RECOMMENDATION 2:
PRIORITY: [Immediate / Short-term / Long-term]
RESPONSIBLE TEAM: [team name]
ACTION: [Specific action to take]
RATIONALE: [Why this addresses the root cause — cite the specific finding]

RECOMMENDATION 3:
PRIORITY: [Immediate / Short-term / Long-term]
RESPONSIBLE TEAM: [team name]
ACTION: [Specific action to take]
RATIONALE: [Why this addresses the root cause — cite the specific finding]

PREVENTIVE MEASURES:
- [Preventive measure 1]
- [Preventive measure 2]
- [Preventive measure 3]
---
If no incident was detected, provide general best-practice recommendations for maintaining data quality.
"""


def recommendation_node(state: AgentState) -> AgentState:
    rca_findings = state.get("rca_findings", "")
    data_quality_findings = state.get("data_quality_findings", "")

    human_prompt = (
        f"ROOT CAUSE ANALYSIS:\n{rca_findings}\n\n"
        f"DATA QUALITY SUMMARY:\n{data_quality_findings}\n\n"
        f"Generate remediation recommendations."
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
