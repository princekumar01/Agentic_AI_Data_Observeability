"""
backend/routers/streaming.py
─────────────────────────────────────────────────────
All /streaming/* endpoints.
Reads from in-memory StreamingState updated by producer/consumer.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.models.schemas import (
    AgentStreamStatus,
    AgentsStatusResponse,
    ConsumerStatus,
    LagDataPoint,
    LagHistoryResponse,
    LiveFinding,
    LiveFindingsResponse,
    ProducerStatus,
    RecentEvent,
    RecentEventsResponse,
    StreamingProgress,
    StreamingStatusResponse,
    ThroughputDataPoint,
    ThroughputHistoryResponse,
    TopicStatus,
    WindowStatusResponse,
)
from backend.services import auth_service, streaming_state_service

router = APIRouter(prefix="/streaming", tags=["streaming"])


def _require_auth(authorization: Optional[str] = Header(default=None)) -> Dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return auth_service.get_current_user(authorization[7:])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _load_config() -> Dict:
    try:
        with open("config.yaml") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def _get_pipeline_status(run_id: str) -> str:
    from backend.routers.pipeline import get_pipeline_runs
    run = get_pipeline_runs().get(run_id)
    return run["status"] if run else "unknown"


@router.get("/status/{run_id}", response_model=StreamingStatusResponse)
def streaming_status(run_id: str, user: Dict = Depends(_require_auth)):
    config = _load_config()
    kafka_cfg = config.get("kafka", {})
    topic = kafka_cfg.get("topic", "clinical_trial_events")
    window_threshold = kafka_cfg.get("window_threshold", 5)

    state = streaming_state_service.get_state(run_id)
    pipeline_status = _get_pipeline_status(run_id)

    if state:
        snap = state.snapshot()
        events_processed = snap["events_received"]
        target = snap["target_events"]
        pending = max(0, target - events_processed)
        pct_complete = round(min(100.0, events_processed / max(1, target) * 100), 1)
        throughput = snap["throughput_history"]
        avg_rate = round(
            sum(p["events_per_sec"] for p in throughput) / max(1, len(throughput)), 2
        ) if throughput else 0.0
        last_event = snap.get("last_published_at") or snap.get("last_consumed_at")

        producer = ProducerStatus(
            status=snap["producer_status"],
            records_sent=snap["events_published"],
            send_rate_msg_per_sec=snap["producer_rate"],
            last_sent=snap["last_published_at"],
            errors=snap["producer_errors"],
        )
        consumer = ConsumerStatus(
            status=snap["consumer_status"],
            records_consumed=snap["events_received"],
            consumer_rate_msg_per_sec=snap["consumer_rate"],
            consumer_lag_avg=snap["consumer_lag_avg"],
            last_consumed=snap["last_consumed_at"],
            errors=snap["consumer_errors"],
        )
    else:
        events_processed = 0
        pending = window_threshold
        pct_complete = 0.0
        avg_rate = 0.0
        last_event = None
        producer = ProducerStatus(status="IDLE", records_sent=0, send_rate_msg_per_sec=0.0, errors=0)
        consumer = ConsumerStatus(status="IDLE", records_consumed=0, consumer_rate_msg_per_sec=0.0, consumer_lag_avg=0.0, errors=0)

    return StreamingStatusResponse(
        run_id=run_id,
        pipeline_status=pipeline_status,
        uptime_seconds=state.snapshot()["uptime_seconds"] if state else 0.0,
        events_processed=events_processed,
        events_per_sec_avg=avg_rate,
        last_event_time=last_event,
        producer=producer,
        consumer=consumer,
        topic=TopicStatus(
            name=topic,
            status="ACTIVE" if pipeline_status == "running" else "IDLE",
            partitions=1,
            replication_factor=1,
            under_replicated=False,
        ),
        progress=StreamingProgress(
            total_target_events=window_threshold,
            events_processed=events_processed,
            events_pending=pending,
            pct_complete=pct_complete,
        ),
    )


@router.get("/lag-history/{run_id}", response_model=LagHistoryResponse)
def lag_history(
    run_id: str,
    window: str = Query("5m"),
    user: Dict = Depends(_require_auth),
):
    state = streaming_state_service.get_state(run_id)
    data_points = []
    if state:
        snap = state.snapshot()
        data_points = [
            LagDataPoint(timestamp=p["timestamp"], consumer_lag=p["consumer_lag"])
            for p in snap.get("lag_history", [])
        ]
    return LagHistoryResponse(
        run_id=run_id,
        window=window,
        lag_threshold=1000,
        data_points=data_points,
    )


@router.get("/throughput-history/{run_id}", response_model=ThroughputHistoryResponse)
def throughput_history(
    run_id: str,
    window: str = Query("5m"),
    user: Dict = Depends(_require_auth),
):
    state = streaming_state_service.get_state(run_id)
    data_points = []
    avg = 0.0
    if state:
        snap = state.snapshot()
        history = snap.get("throughput_history", [])
        data_points = [
            ThroughputDataPoint(timestamp=p["timestamp"], events_per_sec=p["events_per_sec"])
            for p in history
        ]
        if history:
            avg = round(sum(p["events_per_sec"] for p in history) / len(history), 2)
    return ThroughputHistoryResponse(
        run_id=run_id,
        window=window,
        avg_msg_per_sec=avg,
        data_points=data_points,
    )


@router.get("/events/recent/{run_id}", response_model=RecentEventsResponse)
def recent_events(
    run_id: str,
    limit: int = Query(5, ge=1, le=50),
    user: Dict = Depends(_require_auth),
):
    state = streaming_state_service.get_state(run_id)
    events = []
    if state:
        snap = state.snapshot()
        for e in list(snap.get("recent_events", []))[-limit:]:
            events.append(RecentEvent(
                event_id=e.get("event_id", "?"),
                event_type=e.get("event_type", "patient_record"),
                time=e.get("time", ""),
                status=e.get("status", "published"),
            ))
    return RecentEventsResponse(events=events)


@router.get("/agents/status/{run_id}", response_model=AgentsStatusResponse)
def agents_status(run_id: str, user: Dict = Depends(_require_auth)):
    state = streaming_state_service.get_state(run_id)
    agents = []
    if state:
        snap = state.snapshot()
        for a in snap.get("agents_status", []):
            agents.append(AgentStreamStatus(
                name=a.get("name", ""),
                status=a.get("status", "PENDING"),
                last_run=a.get("last_run"),
                confidence=a.get("confidence"),
                findings=a.get("findings"),
            ))
    if not agents:
        default_names = [
            "data_quality_agent", "log_analysis_agent",
            "rca_agent", "recommendation_agent", "compliance_agent",
        ]
        agents = [AgentStreamStatus(name=n, status="PENDING") for n in default_names]
    return AgentsStatusResponse(agents=agents)


@router.get("/ai-findings/live/{run_id}", response_model=LiveFindingsResponse)
def live_ai_findings(
    run_id: str,
    limit: int = Query(5, ge=1, le=50),
    user: Dict = Depends(_require_auth),
):
    state = streaming_state_service.get_state(run_id)
    findings = []
    if state:
        snap = state.snapshot()
        for f in list(snap.get("ai_findings", []))[-limit:]:
            findings.append(LiveFinding(
                id=f.get("id", ""),
                severity=f.get("severity", "info"),
                message=f.get("message", ""),
                agent=f.get("agent", ""),
                timestamp=f.get("timestamp", ""),
            ))
    return LiveFindingsResponse(findings=findings)


@router.get("/window/status/{run_id}", response_model=WindowStatusResponse)
def window_status(run_id: str, user: Dict = Depends(_require_auth)):
    config = _load_config()
    window_size = config.get("kafka", {}).get("window_threshold", 5)
    state = streaming_state_service.get_state(run_id)

    if state:
        snap = state.snapshot()
        ws = snap.get("window_status", {})
        events_in_window = snap.get("events_received", 0)
    else:
        ws = {}
        events_in_window = 0

    now = datetime.now(timezone.utc).isoformat()
    return WindowStatusResponse(
        current_window=1,
        window_start=ws.get("window_start", now),
        window_end=ws.get("window_end"),
        events_in_window=events_in_window,
        window_size=window_size,
        rolling_metrics_status="ACTIVE" if events_in_window > 0 else "WAITING",
    )
