"""
backend/agents/log_analysis_agent.py
─────────────────────────────────────────────────────
Senior DevOps Engineer.
Analyzes ETL logs for Kafka events, stream processor errors,
API timeouts, and preprocessing warnings.

Required output sections:
  ERROR COUNT: / WARNING COUNT: / KAFKA ISSUES: / API ISSUES: /
  DATA QUALITY WARNINGS: / OPERATIONAL STATUS: / SUMMARY:

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

AGENT_NAME = "log_analysis_agent"
REQUIRED_SECTIONS = [
    "ERROR COUNT:", "WARNING COUNT:", "OPERATIONAL STATUS:", "SUMMARY:"
]
MAX_RETRIES = 2


def log_analysis_node(state: AgentState) -> AgentState:
    from llm_config import llm

    run_id = state["run_id"]
    output_dir = state["output_dir"]
    log_text = state.get("sanitized_log_text", "")
    streaming_md = state.get("streaming_metadata", {})
    metrics = state.get("sanitized_metrics", {})

    logger.info(f"[{AGENT_NAME}] Starting | run_id={run_id}")

    prompt = _build_prompt(log_text, streaming_md, metrics)
    _save_prompt(prompt, output_dir)

    response_text = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = llm.invoke(prompt)
            response_text = response.content
        except Exception as exc:
            logger.error(f"[{AGENT_NAME}] LLM call failed (attempt {attempt + 1}): {exc}")
            response_text = _fallback_response(streaming_md, metrics)
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

    return {**state, "log_analysis_findings": response_text}


def _build_prompt(log_text: str, streaming_md: Dict, metrics: Dict) -> str:
    log_summary = metrics.get("log_summary", {})
    # Truncate log to avoid exceeding token limits
    truncated_log = log_text[:8000] if len(log_text) > 8000 else log_text

    return f"""You are a Senior DevOps Engineer specializing in clinical trial data pipelines and Kafka streaming infrastructure.

Analyze the following ETL execution log and streaming metadata.

=== ETL LOG (sanitized) ===
{truncated_log}

=== STREAMING METADATA ===
{json.dumps(streaming_md, indent=2)}

=== LOG SUMMARY ===
Error count:   {log_summary.get('total_errors', 0)}
Warning count: {log_summary.get('total_warnings', 0)}
Info count:    {log_summary.get('total_info', 0)}

=== INSTRUCTIONS ===

Analyze the log for operational issues and provide output using EXACTLY these section headers:

ERROR COUNT: [exact integer from log]
WARNING COUNT: [exact integer from log]
KAFKA ISSUES: [list any Kafka producer/consumer errors found, or "None detected"]
API ISSUES: [list any API timeout or connection issues, or "None detected"]
DATA QUALITY WARNINGS: [list any data quality warnings from preprocessing, or "None detected"]
OPERATIONAL STATUS: [HEALTHY / DEGRADED / CRITICAL]
SUMMARY: [3-4 sentences describing operational health, key issues, and recommended actions]

CONFIDENCE: [0-100]"""


def _fallback_response(streaming_md: Dict, metrics: Dict) -> str:
    log_summary = metrics.get("log_summary", {})
    errors = log_summary.get("total_errors", 0)
    warnings = log_summary.get("total_warnings", 0)
    status = "HEALTHY" if errors == 0 else "DEGRADED"
    return f"""ERROR COUNT: {errors}
WARNING COUNT: {warnings}
KAFKA ISSUES: Schema errors detected: {streaming_md.get('schema_errors_in_stream', 0) if streaming_md else 0}
API ISSUES: API timeouts: {streaming_md.get('api_timeouts', 0) if streaming_md else 0}
DATA QUALITY WARNINGS: {warnings} preprocessing warnings found
OPERATIONAL STATUS: {status}
SUMMARY: Pipeline logged {errors} errors and {warnings} warnings. Consumer processed {streaming_md.get('events_valid', 0) if streaming_md else 0} valid events. Review error entries for root cause.

CONFIDENCE: 60"""


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
