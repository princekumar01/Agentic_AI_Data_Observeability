"""
backend/routers/dashboard.py
All dashboard API endpoints — segregated (per-run) and aggregated (all runs).
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from backend.services import seg_dashboard_service as svc

router = APIRouter(prefix="/seg-dashboard", tags=["seg-dashboard"])


# ──────────────────────────────────────────────────────────────────────────────
# SHARED
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/approved-runs")
def approved_runs():
    """
    Returns list of all approved pipeline runs (run_id, timestamps, record counts).
    Used in the segregated dashboard.
    """
    return svc.get_approved_runs()


# ──────────────────────────────────────────────────────────────────────────────
# SEGREGATED — per run_id
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/run/{run_id}/info")
def run_info(run_id: str):
    """
    Returns metadata for a specific run: started_at, duration, records, model, approved_by.
    Shown in the Pipeline Run ID banner at the top of the segregated dashboard.
    """
    data = svc.get_run_info(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/kpis")
def run_kpis(run_id: str):
    """
    Returns the 3 top KPI cards for a run:
    anomalies_detected, records_processed, compliance_score.
    """
    data = svc.get_segregated_kpis(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/null-rate")
def null_rate(run_id: str):
    """
    Returns null percentage per column with the 5% threshold.
    Powers the Null Rate by Column bar chart.
    Columns exceeding the threshold are highlighted red.
    """
    data = svc.get_null_rate(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/severity-distribution")
def severity_distribution(run_id: str):
    """
    Returns anomaly counts broken down by severity (Critical, High, Medium, Low).
    Powers the Severity Distribution donut chart.
    """
    data = svc.get_severity_distribution(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/agent-confidence")
def agent_confidence(run_id: str):
    """
    Returns confidence score and inference count per agent for this run.
    Powers the Agent Confidence horizontal bar chart.
    """
    data = svc.get_agent_confidence(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/anomaly-summary")
def anomaly_summary(run_id: str):
    """
    Returns per-severity anomaly count with short description for this run.
    Powers the Anomaly Summary panel (replaces trend chart for single runs).
    """
    data = svc.get_anomaly_summary(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


@router.get("/run/{run_id}/token-usage")
def token_usage(run_id: str):
    """
    Returns total tokens (input/output), estimated cost, and per-agent breakdown.
    Powers the Token Usage section — run total card + agents bar chart.
    """
    data = svc.get_token_usage(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return data


# @router.get("/run/{run_id}/pillars")
# def pillars(run_id: str):
#     """
#     Returns scores and status for the 5 observability pillars:
#     Freshness, Schema, Volume, Distribution, Lineage.
#     Powers the Observability Pillars row.
#     """
#     data = svc.get_pillars(run_id)
#     if not data:
#         raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
#     return data


@router.get("/run/{run_id}/findings/{agent}")
def agent_findings(run_id: str, agent: str):
    """
    Returns agent-specific findings list for a run.
    agent must be one of: data_quality, log_analysis, rca, recommendation, compliance.
    Powers the Agent Analysis tabbed section.
    """
    valid = {"data_quality", "log_analysis", "rca", "recommendation", "compliance"}
    if agent not in valid:
        raise HTTPException(status_code=400, detail=f"agent must be one of {valid}")
    return svc.get_agent_findings(run_id, agent)


# ──────────────────────────────────────────────────────────────────────────────
# AGGREGATED — across all approved runs
# ──────────────────────────────────────────────────────────────────────────────

# @router.get("/aggregate/summary")
# def aggregate_summary():
#     """
#     Returns high-level aggregate KPIs across all approved runs:
#     total_runs, total_anomalies, avg_confidence_score, total_token_cost.
#     Powers the Aggregated dashboard KPI cards.
#     """
#     return svc.get_aggregate_summary()


# @router.get("/aggregate/pipeline-runs-over-time")
# def aggregate_pipeline_runs_over_time():
#     """
#     Returns daily completed/failed run counts over the last 7 days.
#     Powers the Pipeline Runs Over Time stacked bar chart.
#     """
#     return svc.get_aggregate_pipeline_runs_over_time()


# @router.get("/aggregate/anomalies-trend")
# def aggregate_anomalies_trend():
#     """
#     Returns daily anomaly counts by severity over the last 7 days.
#     Powers the Anomalies Trend multi-line chart.
#     """
#     return svc.get_aggregate_anomalies_trend()


# @router.get("/aggregate/severity-distribution")
# def aggregate_severity_distribution():
#     """
#     Returns anomaly severity breakdown aggregated across all approved runs.
#     Powers the Severity Distribution donut chart on the Aggregated tab.
#     """
#     return svc.get_aggregate_severity_distribution()


# @router.get("/aggregate/agent-performance")
# def aggregate_agent_performance():
#     """
#     Returns per-agent avg confidence score and total inferences across all runs.
#     Powers the Agent Performance section on the Aggregated tab.
#     """
#     return svc.get_aggregate_agent_performance()


# @router.get("/aggregate/token-usage-by-run")
# def aggregate_token_usage_by_run():
#     """
#     Returns token usage and cost grouped by run_id.
#     Powers the Token Cost by Run bar chart on the Aggregated tab.
#     """
#     return svc.get_aggregate_token_usage_by_run()


# @router.get("/aggregate/run-status-distribution")
# def aggregate_run_status_distribution():
#     """
#     Returns count of runs by status (Approved, Failed, Pending).
#     Powers the Run Status Distribution pie chart.
#     """
#     return svc.get_aggregate_run_status_distribution()


# @router.get("/aggregate/top-anomaly-types")
# def aggregate_top_anomaly_types():
#     """
#     Returns the top 5 most frequent anomaly types across all runs.
#     Powers the Top Anomaly Types ranked list.
#     """
#     return svc.get_aggregate_top_anomaly_types()


# @router.get("/aggregate/pillar-scores")
# def aggregate_pillar_scores():
#     """
#     Returns avg score per observability pillar across all runs, with worst run.
#     Powers the Pillar Health table on the Aggregated tab.
#     """
#     return svc.get_aggregate_pillar_scores()
