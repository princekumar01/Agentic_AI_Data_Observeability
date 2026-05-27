"""
backend/routers/alerts.py
─────────────────────────────────────────────────────
GET  /alerts
GET  /alerts/{alert_id}
POST /alerts/{alert_id}/acknowledge
POST /alerts/{alert_id}/escalate
POST /alerts/read
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.models.schemas import (
    AcknowledgeAlertRequest,
    AcknowledgeAlertResponse,
    AlertDetailResponse,
    AlertHistoryEntry,
    AlertMetrics,
    AlertsListResponse,
    EscalateAlertRequest,
    EscalateAlertResponse,
    ReadAlertRequest,
    ReadAlertResponse,
)
from backend.services import alert_service
from backend.services.auth_service import require_auth_user as _require_auth

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertsListResponse)
def list_alerts(
    severity: str = Query("all"),
    source: str = Query("all"),
    status: str = Query("all"),
    from_dt: Optional[str] = Query(default=None),
    to_dt: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    user: Dict = Depends(_require_auth),
):
    result = alert_service.get_all_alerts(
        severity_filter=severity,
        source_filter=source,
        status_filter=status,
        from_dt=from_dt,
        to_dt=to_dt,
        page=page,
        limit=limit,
    )

    from backend.models.schemas import AlertItem, AlertSummary
    alerts_out = [
        AlertItem(
            id=a["id"],
            severity=a["severity"],
            title=a["title"],
            description=a["description"],
            source=a.get("source", "pipeline"),
            run_id=a.get("run_id"),
            time=a.get("timestamp", a.get("time", "")),
            status=a.get("status", "New"),
        )
        for a in result["alerts"]
    ]

    summary = result["summary"]
    return AlertsListResponse(
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        summary=AlertSummary(
            critical=summary.get("critical", 0),
            high=summary.get("high", 0),
            medium=summary.get("medium", 0),
            low=summary.get("low", 0),
            total_24h=summary.get("total_24h", 0),
            change_pct=summary.get("change_pct", 0.0),
        ),
        alerts=alerts_out,
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse)
def get_alert(alert_id: str, user: Dict = Depends(_require_auth)):
    alert = alert_service.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    history = [
        AlertHistoryEntry(
            action=h.get("action", ""),
            by=h.get("by", "system"),
            at=h.get("at", ""),
        )
        for h in alert.get("history", [])
    ]

    return AlertDetailResponse(
        id=alert["id"],
        severity=alert["severity"],
        is_new=alert.get("status", "New") == "New",
        title=alert["title"],
        source=alert.get("source", "pipeline"),
        triggered_at=alert.get("timestamp", alert.get("time", "")),
        run_id=alert.get("run_id"),
        description=alert.get("description", ""),
        impact="Review required — potential data quality or compliance issue",
        metrics=AlertMetrics(),
        recommended_action="Acknowledge and investigate the underlying pipeline stage",
        history=history,
    )


@router.post("/{alert_id}/acknowledge", response_model=AcknowledgeAlertResponse)
def acknowledge_alert(
    alert_id: str,
    body: AcknowledgeAlertRequest,
    user: Dict = Depends(_require_auth),
):
    ok = alert_service.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=body.acknowledged_by,
        note=body.note,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")

    from datetime import datetime, timezone
    return AcknowledgeAlertResponse(
        success=True,
        alert_id=alert_id,
        status="Acknowledged",
        acknowledged_by=body.acknowledged_by,
        acknowledged_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/{alert_id}/escalate", response_model=EscalateAlertResponse)
def escalate_alert(
    alert_id: str,
    body: EscalateAlertRequest,
    user: Dict = Depends(_require_auth),
):
    ok = alert_service.escalate_alert(
        alert_id=alert_id,
        escalated_by=body.escalated_by,
        reason=body.reason,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")

    from datetime import datetime, timezone
    return EscalateAlertResponse(
        success=True,
        alert_id=alert_id,
        status="Escalated",
        escalated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/read", response_model=ReadAlertResponse)
def mark_read(body: ReadAlertRequest, user: Dict = Depends(_require_auth)):
    ok = alert_service.mark_alert_read(body.alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return ReadAlertResponse(success=True, alert_id=body.alert_id, read=True)
