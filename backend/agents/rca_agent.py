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
Your job is to cross-correlate operational log analysis, data quality assessment, and causal analysis metrics to identify the root cause.

The deterministic causal analysis metrics computed for this run are:
- Site Null Contributions: {site_null_contributions}
- Side Effect Nulls & Severity Correlation: {side_effect_nulls_severity_correlation}
- Recent Deployment History: {recent_deployment_history}

You must form a precise causal hypothesis using these site contributions, severity correlation, and deployment history.
Explain which sites contributed the most nulls, what fraction corresponds to Low severity patients (plausibly no side effects),
and how it correlates with the recent EDC deployment v1.4.2.

Structure your response EXACTLY as follows:
---
INCIDENT DETECTED: [Yes / No]
INCIDENT SEVERITY: [Low / Medium / High / Critical / N/A]

ROOT CAUSE:
[Formulate a precise causal hypothesis using the site contributions, severity correlation, and deployment history.
Explain which sites contributed the most nulls, what fraction corresponds to Low severity patients (plausibly no side effects),
and how it correlates with the recent EDC deployment v1.4.2.]

CONTRIBUTING FACTORS:
- [Factor 1]
- [Factor 2]

IMPACT ASSESSMENT:
[Analyze potential impact on clinical trial data integrity.]
---
Base your analysis entirely on the inputs and metrics provided. Do not speculate or make up other statistics.
"""


def rca_node(state: AgentState) -> AgentState:
    data_quality_findings = state.get("data_quality_findings", "")
    log_analysis_findings = state.get("log_analysis_findings", "")
    metrics = state.get("sanitized_metrics", {})
    causal = metrics.get("causal_analysis", {})
    
    site_nulls = causal.get("site_null_contributions", {})
    se_nulls_sev = causal.get("side_effect_nulls_severity_correlation", {})
    deploy_hist = causal.get("recent_deployment_history", [])

    formatted_system_prompt = SYSTEM_PROMPT.format(
        site_null_contributions=site_nulls,
        side_effect_nulls_severity_correlation=se_nulls_sev,
        recent_deployment_history=deploy_hist
    )

    human_prompt = (
        f"DATA QUALITY ASSESSMENT:\n{data_quality_findings}\n\n"
        f"LOG ANALYSIS ASSESSMENT:\n{log_analysis_findings}\n\n"
        f"Based on all inputs above and the causal analysis metrics, perform a root cause analysis."
    )

    audit_entries = list(state.get("audit_entries", []))

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "rca",
        "event_type": "agent_prompt",
        "stage": "agent_rca",
        "data": {"system_prompt": formatted_system_prompt, "human_prompt": human_prompt},
    })

    response_text = _call_llm_with_retry(
        system_prompt=formatted_system_prompt,
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
