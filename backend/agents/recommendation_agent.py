"""
backend/agents/recommendation_agent.py
─────────────────────────────────────────────────────
Remediation Specialist.
Each recommendation: PRIORITY / RESPONSIBLE TEAM / ACTION / RATIONALE.
Ends with PREVENTIVE MEASURES.

Auto-retries up to 2x if completeness_score < 0.70.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

from backend.agents.state import AgentState
from backend.services import alert_service, token_tracking_service

logger = logging.getLogger(__name__)

AGENT_NAME = "recommendation_agent"
REQUIRED_SECTIONS = ["PRIORITY", "RESPONSIBLE TEAM", "ACTION", "RATIONALE:"]
MAX_RETRIES = 2


def recommendation_node(state: AgentState) -> AgentState:
    from llm_config import llm

    run_id = state["run_id"]
    output_dir = state["output_dir"]
    rca_findings = state.get("rca_findings", "")
    dq_findings = state.get("data_quality_findings", "")
    metrics = state.get("sanitized_metrics", {})

    logger.info(f"[{AGENT_NAME}] Starting | run_id={run_id}")

    prompt = _build_prompt(rca_findings, dq_findings, metrics)
    _save_prompt(prompt, output_dir)

    response_text = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = llm.invoke(prompt)
            response_text = response.content
        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] LLM call failed (attempt {attempt + 1}): {exc}")
            response_text = _fallback_response(metrics)
            break

        completeness = _completeness_score(response_text)
        if completeness >= 0.70 or attempt == MAX_RETRIES:
            break
        logger.warning(f"[{AGENT_NAME}] Completeness {completeness:.2f} < 0.70 — retry {attempt + 1}/{MAX_RETRIES}")

    token_tracking_service.record_token_usage(
        run_id=run_id,
        agent_name=AGENT_NAME,
        input_text=prompt,
        output_text=response_text,
        output_dir=output_dir,
    )

    confidence = _parse_confidence(response_text)
    _save_confidence(confidence, output_dir, AGENT_NAME)
    _save_response(response_text, output_dir)

    if confidence < 60:
        alert_service.write_alert(
            severity="WARNING",
            message=f"Agent '{AGENT_NAME}' confidence {confidence}/100 — below threshold",
            run_id=run_id,
            source=AGENT_NAME,
        )

    logger.info(f"[{AGENT_NAME}] Completed | confidence={confidence}")

    return {**state, "recommendations": response_text}


def _build_prompt(rca_findings: str, dq_findings: str, metrics: Dict) -> str:
    return f"""You are a Remediation Specialist for FDA-regulated clinical trial data systems.

Based on the RCA findings and data quality assessment below, generate actionable remediation recommendations.

=== RCA FINDINGS ===
{rca_findings[:4000]}

=== DATA QUALITY FINDINGS ===
{dq_findings[:2000]}

=== HEALTH CONTEXT ===
Health Score: {metrics.get('health_score', 0)}/100
Total Anomalies: {metrics.get('anomaly_count', 0)}

=== INSTRUCTIONS ===

Provide concrete remediation recommendations. For each recommendation use EXACTLY this format:

PRIORITY: [Immediate / Short-term / Long-term]
RESPONSIBLE TEAM: [Data Engineering / Clinical Operations / QA / IT / Regulatory Affairs]
ACTION: [Specific, concrete action to take]
RATIONALE: [Why this action addresses the root cause]

Provide at least 3 recommendations covering the most critical findings.
After all recommendations:

PREVENTIVE MEASURES:
[Bulleted list of process improvements and monitoring controls to prevent recurrence]

CONFIDENCE: [0-100]"""


def _fallback_response(metrics: Dict) -> str:
    return f"""PRIORITY: Immediate
RESPONSIBLE TEAM: Data Engineering
ACTION: Review and remediate the {metrics.get('anomaly_count', 0)} pipeline anomalies identified.
RATIONALE: Anomalies in clinical trial data can compromise study integrity.

PRIORITY: Short-term
RESPONSIBLE TEAM: Clinical Operations
ACTION: Implement automated data validation checks at point of entry.
RATIONALE: Preventing bad data from entering the pipeline is more efficient than downstream remediation.

PRIORITY: Long-term
RESPONSIBLE TEAM: Regulatory Affairs
ACTION: Schedule FDA 21 CFR Part 11 compliance audit and update SOPs.
RATIONALE: Ensures regulatory compliance and audit readiness.

PREVENTIVE MEASURES:
- Implement real-time null rate alerting thresholds
- Add Kafka consumer lag monitoring dashboards
- Establish baseline drift detection with quarterly recalibration
- Train clinical staff on data entry standards

CONFIDENCE: 65"""


def _completeness_score(text: str) -> float:
    found = sum(1 for s in REQUIRED_SECTIONS if s in text)
    return found / len(REQUIRED_SECTIONS)


def _parse_confidence(text: str) -> int:
    match = re.search(r"CONFIDENCE:\s*\[?(\d+)\]?", text)
    if match:
        return min(100, max(0, int(match.group(1))))
    return 70


def _save_prompt(prompt: str, output_dir: str) -> None:
    d = os.path.join(output_dir, "prompts")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{AGENT_NAME}.txt"), "w", encoding="utf-8") as fh:
        fh.write(prompt)


def _save_response(response: str, output_dir: str) -> None:
    d = os.path.join(output_dir, "responses")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{AGENT_NAME}.json"), "w", encoding="utf-8") as fh:
        json.dump({"agent": AGENT_NAME, "response": response, "saved_at": datetime.now(timezone.utc).isoformat()}, fh, indent=2)


def _save_confidence(score: int, output_dir: str, agent_name: str) -> None:
    path = os.path.join(output_dir, "agent_confidence.json")
    data: Dict = {}
    if os.path.exists(path):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except Exception:
            data = {}
    data[agent_name] = score
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
