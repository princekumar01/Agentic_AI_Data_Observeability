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

CRITICAL — How to determine pillar STATUS:

1. **Schema pillar**: The authoritative source is `pillar_schema.dtype_checks` — each
   column has a `passed: True/False` flag. If every column has `passed: True` AND
   `missing_columns` is empty AND `duplicate_patient_ids` is 0, then STATUS = OK.
   Do NOT invent schema anomalies from the `actual` type string. The `actual` field
   describes what was validated, not what's wrong. If `passed: True`, the schema
   is correct for that column regardless of what the type string looks like.

2. **Distribution pillar**: STATUS = ANOMALY if `outlier_count > 0` OR `drift_detected: True`
   for any numeric column. STATUS = OK only if both are clean. Clinical alerts (e.g.,
   `clinical_alert_count > 0`) are always ANOMALY — these are patient safety signals.

3. **Lineage pillar**: STATUS = WARNING if `warning_count > 0` (and `error_count == 0`).
   STATUS = ANOMALY if `error_count > 0`. STATUS = OK if both are 0.

4. **Freshness and Volume**: trust the `_ok` / `_anomaly` boolean flags directly.

For each pillar, describe its severity (Low/Medium/High/Critical) and explain what it
means in the context of clinical trials.

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
