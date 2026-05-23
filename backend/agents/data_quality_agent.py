"""
backend/agents/data_quality_agent.py
─────────────────────────────────────────────────────
Clinical Data Quality Specialist.
Evaluates all 5 observability pillars and streaming-specific metrics.

Required output sections:
  PILLAR: / STATUS: / FINDING: per pillar
  OVERALL SEVERITY:
  SUMMARY:

Auto-retries up to 2x if completeness_score < 0.70.
Parses CONFIDENCE: [0-100] from response.
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

AGENT_NAME = "data_quality_agent"
REQUIRED_SECTIONS = ["PILLAR:", "STATUS:", "FINDING:", "OVERALL SEVERITY:", "SUMMARY:"]
MAX_RETRIES = 2


def data_quality_node(state: AgentState) -> AgentState:
    from llm_config import llm  # imported here to respect module-level singleton

    run_id = state["run_id"]
    output_dir = state["output_dir"]
    metrics = state.get("sanitized_metrics", {})
    streaming_md = state.get("streaming_metadata", {})

    logger.info(f"[{AGENT_NAME}] Starting | run_id={run_id}")

    prompt = _build_prompt(metrics, streaming_md)
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
        logger.warning(
            f"[{AGENT_NAME}] Completeness {completeness:.2f} < 0.70 — retry {attempt + 1}/{MAX_RETRIES}"
        )

    # Token tracking
    token_tracking_service.record_token_usage(
        run_id=run_id,
        agent_name=AGENT_NAME,
        input_text=prompt,
        output_text=response_text,
        output_dir=output_dir,
    )

    # Confidence parsing
    confidence = _parse_confidence(response_text)
    _save_confidence(confidence, output_dir, AGENT_NAME)
    _save_response(response_text, output_dir)

    # Alert if confidence low
    if confidence < 60:
        alert_service.write_alert(
            severity="WARNING",
            message=f"Agent '{AGENT_NAME}' confidence {confidence}/100 — below threshold",
            run_id=run_id,
            source=AGENT_NAME,
        )

    logger.info(f"[{AGENT_NAME}] Completed | confidence={confidence}")

    return {
        **state,
        "data_quality_findings": response_text,
    }


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(metrics: Dict[str, Any], streaming_md: Dict[str, Any]) -> str:
    volume = metrics.get("volume", {})
    freshness = metrics.get("freshness", {})
    schema = metrics.get("schema", {})
    distribution = metrics.get("distribution", {})
    lineage = metrics.get("lineage", {})
    streaming = metrics.get("streaming", {})
    log_summary = metrics.get("log_summary", {})

    prompt = f"""You are a Clinical Data Quality Specialist with expertise in FDA-regulated clinical trials.

Analyze the following observability metrics from a real-time Kafka streaming pipeline and evaluate all 5 pillars.

=== METRICS REPORT ===

HEALTH SCORE: {metrics.get('health_score', 0)}/100 ({metrics.get('health_label', 'Unknown')})
TOTAL ROWS: {metrics.get('total_rows', 0)}
ANOMALY COUNT: {metrics.get('anomaly_count', 0)}
ANOMALIES: {json.dumps(metrics.get('anomalies', []), indent=2)}

PILLAR 1 — VOLUME:
{json.dumps(volume, indent=2)}

PILLAR 2 — FRESHNESS:
{json.dumps(freshness, indent=2)}

PILLAR 3 — SCHEMA / NULL DETECTION:
{json.dumps(schema, indent=2)}

PILLAR 4 — DISTRIBUTION:
{json.dumps(distribution, indent=2)}

PILLAR 5 — LINEAGE / DRIFT DETECTION:
{json.dumps(lineage, indent=2)}

STREAMING METRICS:
  - events_in_window: {streaming.get('events_in_window', 0)}
  - event_arrival_latency_avg_ms: {freshness.get('event_arrival_latency_avg_ms', 0)}
  - schema_errors_in_stream: {streaming.get('schema_errors_in_stream', 0)}
  - consumer_lag_avg: {streaming.get('consumer_lag_avg', 0)}
  - events_valid: {streaming.get('events_valid', 0)}
  - events_invalid: {streaming.get('events_invalid', 0)}

LOG SUMMARY:
  - Total Warnings: {log_summary.get('total_warnings', 0)}
  - Total Errors: {log_summary.get('total_errors', 0)}

=== INSTRUCTIONS ===

Provide a structured analysis using EXACTLY these headers for each of the 5 pillars:

PILLAR: [Pillar name]
STATUS: [PASS / WARN / FAIL]
FINDING: [Detailed finding with exact metric values]

After all 5 pillars:

OVERALL SEVERITY: [Critical / High / Medium / Low]
SUMMARY: [3-5 sentence executive summary for clinical trial compliance officers]

CONFIDENCE: [0-100]"""
    return prompt


def _fallback_response(metrics: Dict) -> str:
    health = metrics.get("health_score", 0)
    return f"""PILLAR: Volume
STATUS: {'PASS' if metrics.get('volume', {}).get('volume_ok') else 'FAIL'}
FINDING: {metrics.get('total_rows', 0)} rows processed.

PILLAR: Freshness
STATUS: {'PASS' if metrics.get('freshness', {}).get('freshness_ok') else 'WARN'}
FINDING: Event arrival latency avg {metrics.get('freshness', {}).get('event_arrival_latency_avg_ms', 0):.1f}ms.

PILLAR: Schema
STATUS: {'PASS' if not metrics.get('schema', {}).get('schema_issues') else 'WARN'}
FINDING: {len(metrics.get('schema', {}).get('schema_issues', []))} schema issues detected.

PILLAR: Distribution
STATUS: WARN
FINDING: {len(metrics.get('distribution', {}).get('outlier_stats', {}))} columns checked for outliers.

PILLAR: Lineage
STATUS: {'PASS' if metrics.get('lineage', {}).get('baseline_loaded') else 'WARN'}
FINDING: Drift detection {'completed' if metrics.get('lineage', {}).get('baseline_loaded') else 'skipped — no baseline'}.

OVERALL SEVERITY: {'Critical' if health < 60 else 'High' if health < 75 else 'Medium'}
SUMMARY: Pipeline health score is {health}/100. Review individual pillar findings for remediation steps.

CONFIDENCE: 55"""


def _completeness_score(text: str) -> float:
    found = sum(1 for s in REQUIRED_SECTIONS if s in text)
    return found / len(REQUIRED_SECTIONS)


def _parse_confidence(text: str) -> int:
    match = re.search(r"CONFIDENCE:\s*\[?(\d+)\]?", text)
    if match:
        return min(100, max(0, int(match.group(1))))
    return 70  # default if not parseable


def _save_prompt(prompt: str, output_dir: str) -> None:
    prompts_dir = os.path.join(output_dir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    with open(os.path.join(prompts_dir, f"{AGENT_NAME}.txt"), "w", encoding="utf-8") as fh:
        fh.write(prompt)


def _save_response(response: str, output_dir: str) -> None:
    responses_dir = os.path.join(output_dir, "responses")
    os.makedirs(responses_dir, exist_ok=True)
    path = os.path.join(responses_dir, f"{AGENT_NAME}.json")
    with open(path, "w", encoding="utf-8") as fh:
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
