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

SYSTEM_PROMPT = """You are the single Final Verdict Agent specializing in clinical trial data reporting and GCP/HIPAA compliance.
Your job is to review all pipeline findings (Data Quality, Log Analysis, RCA, Recommendations) and render a single final verdict.

You must output a structured JSON block at the very beginning of your response, followed by standard compliance sections.

The JSON block must follow this EXACT format:
```json
{{
  "verdict": "APPROVED" | "APPROVED_WITH_CAVEATS" | "REJECTED",
  "score": int,
  "blocking_issues": ["list of critical/blocking issues, e.g. PII leaks, critical ETL failures"],
  "non_blocking_issues": ["list of minor/non-blocking issues, e.g. mild outliers, minor nulls"]
}}
```

Rules for the score and verdict:
1. If there are any remaining PHI/PII or critical ETL errors, the verdict must be REJECTED, and the score must be under 60 (e.g. 55).
2. If there are minor anomalies (like outliers, drift, or nullable side_effect nulls) but no PII and the data is safe to use, the verdict must be APPROVED_WITH_CAVEATS, and the score must be between 60 and 90 (e.g. 85).
3. If there are no issues at all, the verdict must be APPROVED, and the score must be 100.

After the JSON block, you must output the standard GCP/HIPAA compliance fields EXACTLY in this format for backwards compatibility:
---
COMPLIANCE STATUS: [APPROVED / APPROVED_WITH_CAVEATS / NEEDS REVISION]

PHI/PII CHECK: [CLEAN / CONTAINS PHI — MUST NOT PROCEED]

COMPLETENESS CHECK: [Complete / Missing: list missing sections]

GCP ALIGNMENT: [Aligned / Issues: describe issues]

REGULATORY NOTES:
[Any specific notes for the clinical data manager reviewing this report.
Explain the rationale for the verdict and final score.]

FINAL RECOMMENDATION: [APPROVE FOR REVIEW / RETURN FOR REVISION]
---
"""


def compliance_node(state: AgentState) -> AgentState:
    data_quality = state.get("data_quality_findings", "")
    log_analysis = state.get("log_analysis_findings", "")
    rca = state.get("rca_findings", "")
    recommendations = state.get("recommendations", "")

    human_prompt = (
        f"Please review the following findings and render the final verdict and regulatory compliance check:\n\n"
        f"DATA QUALITY FINDINGS:\n{data_quality}\n\n"
        f"LOG ANALYSIS FINDINGS:\n{log_analysis}\n\n"
        f"ROOT CAUSE ANALYSIS:\n{rca}\n\n"
        f"RECOMMENDATIONS:\n{recommendations}\n\n"
        f"Review the above and output the structured JSON verdict followed by regulatory notes."
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

    # Parse verdict JSON from response_text and update the overall health score dynamically
    import json
    import re
    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            verdict_data = json.loads(json_match.group(1))
            verdict_score = verdict_data.get("score")
            if verdict_score is not None:
                state["sanitized_metrics"]["overall_health_score"] = int(verdict_score)
    except Exception:
        pass

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
