"""
dashboard_service.py
Aggregates all run artifacts into a single payload for the dashboard endpoint.
Reads from the output/runs/{run_id}/ directory.
"""

import os
import json
from typing import Optional


def load_dashboard_data(run_id: str, runs_dir: str) -> Optional[dict]:
    """
    Load all artifacts for a completed, approved run and return
    a structured dashboard payload.

    Returns None if the run directory or required files don't exist.
    """
    run_dir = os.path.join(runs_dir, run_id)
    if not os.path.isdir(run_dir):
        return None

    # ── Load audit trail ─────────────────────────────────────────────────────
    audit = _load_json(run_dir, "audit_trail.json")
    if not audit:
        return None

    # ── Load sanitized metrics ───────────────────────────────────────────────
    metrics = _load_json(run_dir, "sanitized_metrics.json")
    if not metrics:
        metrics = _load_json(run_dir, "metrics.json") or {}

    # ── Load incident report ─────────────────────────────────────────────────
    incident_report_md = _load_text(run_dir, "incident_report.md") or ""

    # ── Extract agent findings from audit trail ──────────────────────────────
    agent_findings = _extract_agent_findings(audit)

    # ── Build audit summary ──────────────────────────────────────────────────
    hitl = audit.get("hitl_decision", {})
    agent_calls = [
        e for e in audit.get("entries", []) if e.get("event_type") == "agent_response"
    ]
    audit_summary = {
        "total_entries": len(audit.get("entries", [])),
        "agent_calls": len(agent_calls),
        "pipeline_started_at": audit.get("pipeline_started_at"),
        "pipeline_completed_at": audit.get("pipeline_completed_at"),
        "reviewer_id": hitl.get("reviewer_id"),
        "reviewer_notes": hitl.get("reviewer_notes"),
        "pipeline_approved_at": hitl.get("decided_at"),
    }

    # ── Build chart data ─────────────────────────────────────────────────────
    pillar_chart_data = _build_chart_data(metrics)

    return {
        "run_id": run_id,
        "health_score": metrics.get("overall_health_score", 0),
        "metrics": metrics,
        "agent_findings": agent_findings,
        "incident_report_md": incident_report_md,
        "audit_summary": audit_summary,
        "pillar_chart_data": pillar_chart_data,
    }


def list_runs(runs_dir: str) -> list:
    """Return a list of all run directories with their metadata."""
    if not os.path.isdir(runs_dir):
        return []

    runs = []
    for run_id in sorted(os.listdir(runs_dir), reverse=True):
        run_dir = os.path.join(runs_dir, run_id)
        if not os.path.isdir(run_dir):
            continue
        audit = _load_json(run_dir, "audit_trail.json")
        if audit:
            runs.append(
                {
                    "run_id": run_id,
                    "started_at": audit.get("pipeline_started_at", ""),
                    "status": audit.get("pipeline_status", "unknown"),
                }
            )
    return runs


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(run_dir: str, filename: str) -> Optional[dict]:
    path = os.path.join(run_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_text(run_dir: str, filename: str) -> Optional[str]:
    path = os.path.join(run_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _extract_agent_findings(audit: dict) -> dict:
    """Extract agent response content from audit entries."""
    agent_map = {
        "data_quality": "",
        "log_analysis": "",
        "rca": "",
        "recommendation": "",
        "compliance": "",
    }
    for entry in audit.get("entries", []):
        if entry.get("event_type") == "agent_response":
            agent = entry.get("agent", "")
            if agent in agent_map:
                agent_map[agent] = entry.get("data", {}).get("response", "")
    return agent_map


def _build_chart_data(metrics: dict) -> dict:
    """Build structured chart data from sanitized metrics."""
    dist = metrics.get("pillar_distribution", {})
    vol = metrics.get("pillar_volume", {})
    schema = metrics.get("pillar_schema", {})
    freshness = metrics.get("pillar_freshness", {})
    lineage = metrics.get("pillar_lineage", {})

    return {
        "freshness": {
            "days_since_last_visit": freshness.get("days_since_last_visit", 0),
            "freshness_ok": freshness.get("freshness_ok", True),
            "most_recent_visit_date": freshness.get("most_recent_visit_date", ""),
        },
        "volume": {
            "row_count": vol.get("row_count", 0),
            "expected_row_count": vol.get("expected_row_count", 0),
            "volume_delta_pct": vol.get("volume_delta_pct", 0.0),
            "volume_anomaly": vol.get("volume_anomaly", False),
        },
        "schema": {
            "null_report": schema.get("null_report", {}),
            "dtype_checks": schema.get("dtype_checks", {}),
            "duplicate_patient_ids": schema.get("duplicate_patient_ids", 0),
            "missing_columns": schema.get("missing_columns", []),
        },
        "distribution": {
            "glucose_level": dist.get("glucose_level", {}),
            "age": dist.get("age", {}),
            "severity_distribution": dist.get("severity_distribution", {}),
            "severity_counts": dist.get("severity_counts", {}),
            "side_effect_counts": dist.get("side_effect_counts", {}),
            "critical_event_pct": dist.get("critical_event_pct", 0.0),
            "drift_detection": dist.get("drift_detection", {}),
        },
        "lineage": {
            "warning_count": lineage.get("warning_count", 0),
            "error_count": lineage.get("error_count", 0),
        },
    }
