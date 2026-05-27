"""
backend/routers/dashboard.py
─────────────────────────────────────────────────────
All /dashboard/* endpoints.
Returns 403 for run-specific data if run not approved.
"""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.models.schemas import (
    AgentsPerformanceResponse,
    AnomaliesBySeverityResponse,
    AnomalyTrendResponse,
    DashboardSummaryResponse,
    PipelineHealthResponse,
    PipelineRunsOverTimeResponse,
    RecentAlertsDashboardResponse,
    RecentAlertItem,
    RunStatusDistributionResponse,
    RunTokensResponse,
    TokenUsageDashboardResponse,
    TopAnomalyTypesResponse,
)
from backend.services import dashboard_service, alert_service
from backend.services.auth_service import require_auth_user as _require_auth

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def summary(period: str = Query("24h"), user: Dict = Depends(_require_auth)):
    data = dashboard_service.get_summary(period)
    return DashboardSummaryResponse(**data)


@router.get("/pipeline-runs-over-time", response_model=PipelineRunsOverTimeResponse)
def pipeline_runs_over_time(
    period: str = Query("24h"),
    granularity: str = Query("hourly"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_pipeline_runs_over_time(period, granularity)
    return PipelineRunsOverTimeResponse(**data)


@router.get("/anomalies-by-severity", response_model=AnomaliesBySeverityResponse)
def anomalies_by_severity(
    period: str = Query("24h"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_anomalies_by_severity(period)
    return AnomaliesBySeverityResponse(**data)


@router.get("/agents-performance", response_model=AgentsPerformanceResponse)
def agents_performance(
    period: str = Query("24h"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_agents_performance(period)
    return AgentsPerformanceResponse(**data)


@router.get("/token-usage", response_model=TokenUsageDashboardResponse)
def token_usage_dashboard(
    period: str = Query("24h"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_token_usage_summary(period)
    return TokenUsageDashboardResponse(**data)


@router.get("/pipeline-health", response_model=PipelineHealthResponse)
def pipeline_health(user: Dict = Depends(_require_auth)):
    data = dashboard_service.get_pipeline_health()
    return PipelineHealthResponse(**data)


@router.get("/anomaly-trend", response_model=AnomalyTrendResponse)
def anomaly_trend(
    period: str = Query("7d"),
    granularity: str = Query("daily"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_anomalies_trend(period, granularity)
    return AnomalyTrendResponse(**data)


@router.get("/top-anomaly-types", response_model=TopAnomalyTypesResponse)
def top_anomaly_types(
    period: str = Query("24h"),
    limit: int = Query(5, ge=1, le=20),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_top_anomaly_types(period, limit)
    return TopAnomalyTypesResponse(**data)


@router.get("/run-status-distribution", response_model=RunStatusDistributionResponse)
def run_status_distribution(
    period: str = Query("24h"),
    user: Dict = Depends(_require_auth),
):
    data = dashboard_service.get_run_status_distribution(period)
    return RunStatusDistributionResponse(**data)


@router.get("/recent-alerts", response_model=RecentAlertsDashboardResponse)
def recent_alerts_dashboard(
    limit: int = Query(5, ge=1, le=20),
    user: Dict = Depends(_require_auth),
):
    result = alert_service.get_all_alerts(page=1, limit=limit)
    alerts_out = [
        RecentAlertItem(
            id=a["id"],
            severity=a["severity"],
            title=a["title"],
            agent=a.get("source", "pipeline"),
            time=a.get("timestamp", ""),
        )
        for a in result["alerts"]
    ]
    return RecentAlertsDashboardResponse(alerts=alerts_out)


@router.get("/run-tokens/{run_id}", response_model=RunTokensResponse)
def run_tokens(run_id: str, user: Dict = Depends(_require_auth)):
    try:
        data = dashboard_service.get_run_tokens(run_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return RunTokensResponse(**data)
