"""
log_analysis_agent.py
Analyzes the sanitized ETL execution log to identify failure patterns,
errors, and operational issues.
"""

import re
import time
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import llm
from backend.agents.state import AgentState


def _enforce_deterministic_counts(response_text: str, error_count: int, warning_count: int, log_text: str) -> str:
    """Force the count fields and lists to deterministic Python-computed values,
    preventing any hallucinated error/warning bullet points or mismatch with the counts."""
    import re
    
    # Extract actual warning and error lines from the log
    warnings_in_log = []
    errors_in_log = []
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "| WARNING" in line:
            warnings_in_log.append(line)
        elif "| ERROR" in line or "| CRITICAL" in line:
            errors_in_log.append(line)
            
    # Try to extract OPERATIONAL STATUS and SUMMARY from the LLM's raw response
    status_match = re.search(r"OPERATIONAL\s*STATUS\s*:\s*(.*)", response_text, re.IGNORECASE)
    summary_match = re.search(r"SUMMARY\s*:\s*(.*)", response_text, re.IGNORECASE)
    
    status = "Degraded"
    if status_match:
        status = status_match.group(1).strip()
        # Clean up brackets/markdown/formatting from status
        status = re.sub(r"[\[\]\*\-\_]", "", status)
        
    summary = "Pipeline completed with warnings."
    if summary_match:
        summary = summary_match.group(1).strip()
        # Clean up brackets from summary
        summary = re.sub(r"[\[\]]", "", summary)
        
    # Reconstruct the response with absolute deterministic correctness
    error_list = "\n".join([f"- {line}" for line in errors_in_log]) if errors_in_log else "- None"
    warning_list = "\n".join([f"- {line}" for line in warnings_in_log]) if warnings_in_log else "- None"
    
    reconstructed = f"""---
ERROR COUNT: {error_count}
WARNING COUNT: {warning_count}

ERRORS FOUND:
{error_list}

WARNINGS FOUND:
{warning_list}

OPERATIONAL STATUS: {status}
SUMMARY: {summary}
---"""
    return reconstructed

SYSTEM_PROMPT = """You are a Senior DevOps Engineer with expertise in clinical data pipeline operations.
Your job is to analyze the ETL execution log from a clinical trial data pipeline and identify:
1. Any errors that occurred during execution
2. Any warnings that may indicate data quality issues
3. Performance concerns (slow steps, timeouts, retries)
4. Patterns that correlate with data anomalies

Structure your response EXACTLY as follows:
---
ERROR COUNT: {error_count}
WARNING COUNT: {warning_count}

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
    metrics = state.get("sanitized_metrics", {})
    lineage = metrics.get("pillar_lineage", {})
    warning_count = lineage.get("warning_count", 0)
    error_count = lineage.get("error_count", 0)

    formatted_system_prompt = SYSTEM_PROMPT.format(
        error_count=error_count,
        warning_count=warning_count
    )

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
        "data": {"system_prompt": formatted_system_prompt, "human_prompt": human_prompt},
    })

    raw_response = _call_llm_with_retry(
        system_prompt=formatted_system_prompt,
        human_prompt=human_prompt,
        agent_name="log_analysis",
    )

    # Force the count fields to deterministic Python-computed values, regardless
    # of what the LLM wrote. Closes the loophole where the LLM ignores the
    # prompt template and hallucinates a different count.
    response_text = _enforce_deterministic_counts(raw_response, error_count, warning_count, log_text)

    audit_entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "log_analysis",
        "event_type": "agent_response",
        "stage": "agent_log_analysis",
        "data": {
            "response": response_text,
            "raw_response": raw_response,
            "counts_enforced": {
                "error_count": error_count,
                "warning_count": warning_count,
            },
        },
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
