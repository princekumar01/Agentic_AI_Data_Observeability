"""
data_quality_agent.py
Analyzes the sanitized Metrics JSON across all 5 observability pillars.
"""

import json
import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState

SYSTEM_PROMPT = """You are a Clinical Data Quality Specialist working on a pharmaceutical clinical trial data pipeline.
Your job is to analyze the data quality metrics JSON and identify anomalies across all five observability pillars:
Freshness, Volume, Schema, Distribution, and Lineage.

For each pillar, determine if there is an anomaly, describe its severity (Low/Medium/High/Critical),
and explain what it means in the context of clinical trials.

Structure your response EXACTLY as follows:
---
PILLAR: Freshness
STATUS: [OK / WARNING / ANOMALY]
FINDING: [1-2 sentence description]

PILLAR: Volume
STATUS: [OK / WARNING / ANOMALY]
FINDING: [1-2 sentence description]

PILLAR: Schema
STATUS: [OK / WARNING / ANOMALY]
FINDING: [1-2 sentence description]

PILLAR: Distribution
STATUS: [OK / WARNING / ANOMALY]
FINDING: [1-2 sentence description]

PILLAR: Lineage
STATUS: [OK / WARNING / ANOMALY]
FINDING: [1-2 sentence description]

OVERALL SEVERITY: [Low / Medium / High / Critical]
SUMMARY: [2-3 sentence executive summary of data quality]
---
Only report what the metrics show. Do not fabricate findings. Do not include patient names or IDs.
"""


def data_quality_node(state: AgentState) -> AgentState:
    metrics = state["sanitized_metrics"]
    metrics_str = json.dumps(metrics, indent=2, default=str)

    human_prompt = (
        f"Here is the sanitized Metrics JSON from today's clinical trial data pipeline run:\n\n"
        f"{metrics_str}\n\n"
        f"Analyze the above metrics and provide your data quality assessment."
    )

    audit_entries = list(state.get("audit_entries", []))

    # Log prompt to audit
    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "data_quality",
        "event_type": "agent_prompt",
        "stage": "agent_data_quality",
        "data": {"system_prompt": SYSTEM_PROMPT, "human_prompt": human_prompt},
    })

    # Call LLM with retry
    response_text = _call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        human_prompt=human_prompt,
        agent_name="data_quality",
    )

    # Log response to audit
    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "data_quality",
        "event_type": "agent_response",
        "stage": "agent_data_quality",
        "data": {"response": response_text},
    })

    state["data_quality_findings"] = response_text
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
