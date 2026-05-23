"""
backend/agents/rca_agent.py
─────────────────────────────────────────────────────
Root Cause Analysis Specialist.
Cross-correlates metrics findings AND log findings.
Lists incidents in PRIORITY ORDER: Critical → High → Medium → Low.
Each incident cites exact metric value AND exact log entry.

Required output sections:
  TOTAL INCIDENTS DETECTED: N
  INCIDENT: / ROOT CAUSE: / EVIDENCE: / IMPACT:
  OVERALL PIPELINE HEALTH:
  ROOT CAUSE SUMMARY:

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

AGENT_NAME = "rca_agent"
REQUIRED_SECTIONS = [
    "TOTAL INCIDENTS DETECTED:",
    "ROOT CAUSE",
    "EVIDENCE:",
]
MAX_RETRIES = 2


def rca_node(state: AgentState) -> AgentState:
    from llm_config import llm

    run_id = state["run_id"]
    output_dir = state["output_dir"]
    dq_findings = state.get("data_quality_findings", "")
    log_findings = state.get("log_analysis_findings", "")
    metrics = state.get("sanitized_metrics", {})

    logger.info(f"[{AGENT_NAME}] Starting | run_id={run_id}")

    prompt = _build_prompt(dq_findings, log_findings, metrics)
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

    # Write Critical/High alerts
    incident_count = _parse_incident_count(response_text)
    if incident_count > 0:
        alert_service.write_alert(
            severity="CRITICAL" if incident_count >= 3 else "WARNING",
            message=f"RCA agent detected {incident_count} incidents in run {run_id}",
            run_id=run_id,
            source=AGENT_NAME,
        )

    if confidence < 60:
        alert_service.write_alert(
            severity="WARNING",
            message=f"Agent '{AGENT_NAME}' confidence {confidence}/100 — below threshold",
            run_id=run_id,
            source=AGENT_NAME,
        )

    logger.info(f"[{AGENT_NAME}] Completed | confidence={confidence} incidents={incident_count}")

    return {**state, "rca_findings": response_text}


def _build_prompt(dq_findings: str, log_findings: str, metrics: Dict) -> str:
    return f"""You are a Root Cause Analysis (RCA) Specialist for FDA-regulated clinical trial data pipelines.

Cross-correlate the data quality findings and log analysis findings below to identify root causes.
Cite EXACT metric values and EXACT log entries as evidence.

=== DATA QUALITY AGENT FINDINGS ===
{dq_findings[:4000]}

=== LOG ANALYSIS AGENT FINDINGS ===
{log_findings[:3000]}

=== SUPPORTING METRICS ===
Health Score: {metrics.get('health_score', 0)}/100
Anomaly Count: {metrics.get('anomaly_count', 0)}
Anomalies: {json.dumps(metrics.get('anomalies', []))}

=== INSTRUCTIONS ===

List incidents in PRIORITY ORDER: Critical → High → Medium → Low.
For each incident provide:

TOTAL INCIDENTS DETECTED: [N]

[Repeat for each incident, highest priority first:]
INCIDENT: [Short name] | PRIORITY: [Critical/High/Medium/Low]
ROOT CAUSE: [Concise root cause]
EVIDENCE: [Exact metric value or exact log entry that proves this]
IMPACT: [Clinical or operational impact]

After all incidents:
OVERALL PIPELINE HEALTH: [CRITICAL / DEGRADED / ACCEPTABLE / HEALTHY]
ROOT CAUSE SUMMARY: [2-3 sentences summarizing the most critical root cause and recommended escalation path]

CONFIDENCE: [0-100]"""


def _fallback_response(metrics: Dict) -> str:
    anomalies = metrics.get("anomalies", [])
    count = len(anomalies)

    if anomalies:
        incident_lines = []
        for a in anomalies[:3]:
            incident_lines.append(
                "INCIDENT: "
                f"{a[:60]}"
                " | PRIORITY: High\n"
                "ROOT CAUSE: Automated detection\n"
                f"EVIDENCE: {a}\n"
                "IMPACT: Data quality risk\n"
            )
        incident_block = "\n".join(incident_lines)
    else:
        incident_block = "No incidents detected."

    health = "DEGRADED" if count > 0 else "HEALTHY"
    return (
        f"TOTAL INCIDENTS DETECTED: {count}\n\n"
        f"{incident_block}\n\n"
        f"OVERALL PIPELINE HEALTH: {health}\n"
        f"ROOT CAUSE SUMMARY: {count} pipeline anomalies identified. Review individual incident findings for specific remediation actions.\n\n"
        "CONFIDENCE: 55"
    )


def _parse_incident_count(text: str) -> int:
    match = re.search(r"TOTAL INCIDENTS DETECTED:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return 0


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
