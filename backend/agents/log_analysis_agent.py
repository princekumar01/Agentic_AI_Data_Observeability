"""
log_analysis_agent.py
Analyzes the sanitized ETL execution log to identify failure patterns,
errors, and operational issues.
"""

import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState

SYSTEM_PROMPT = """You are a Senior DevOps Engineer with expertise in clinical data pipeline operations.
Your job is to analyze the ETL execution log from a clinical trial data pipeline and identify:
1. Any errors that occurred during execution
2. Any warnings that may indicate data quality issues
3. Performance concerns (slow steps, timeouts, retries)
4. Patterns that correlate with data anomalies

Structure your response EXACTLY as follows:
---
ERROR COUNT: [number]
WARNING COUNT: [number]

ERRORS FOUND:
- [timestamp] [error message] [brief explanation]
(write "None" if no errors)

WARNINGS FOUND:
- [timestamp] [warning message] [brief explanation]
(write "None" if no warnings)

OPERATIONAL STATUS: [Healthy / Degraded / Failed]
SUMMARY: [2-3 sentence summary of operational health during this pipeline run]
---
Only report what is in the log. Do not fabricate log entries or timestamps.
Do not include any patient identifiers in your response.
"""


def log_analysis_node(state: AgentState) -> AgentState:
    log_text = state["sanitized_log_text"]

    human_prompt = (
        f"Here is the sanitized ETL execution log from today's clinical trial data pipeline run:\n\n"
        f"{log_text}\n\n"
        f"Analyze the log and provide your operational assessment."
    )

    audit_entries = list(state.get("audit_entries", []))

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "log_analysis",
        "event_type": "agent_prompt",
        "stage": "agent_log_analysis",
        "data": {"system_prompt": SYSTEM_PROMPT, "human_prompt": human_prompt},
    })

    response_text = _call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        human_prompt=human_prompt,
        agent_name="log_analysis",
    )

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "log_analysis",
        "event_type": "agent_response",
        "stage": "agent_log_analysis",
        "data": {"response": response_text},
    })

    state["log_analysis_findings"] = response_text
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
