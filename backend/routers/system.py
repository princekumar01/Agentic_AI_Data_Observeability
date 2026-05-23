"""
backend/routers/system.py
─────────────────────────────────────────────────────
GET /system/status
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter

from backend.kafka.topics import check_kafka_available
from backend.models.schemas import ServiceStatuses, SystemStatusResponse

router = APIRouter(prefix="/system", tags=["system"])

_start_time = time.time()


@router.get("/status", response_model=SystemStatusResponse)
def system_status():
    import yaml  # type: ignore

    # Load Kafka bootstrap from config
    bootstrap = "localhost:9092"
    cfg_path = "config.yaml"
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as fh:
                cfg = yaml.safe_load(fh)
            bootstrap = cfg.get("kafka", {}).get("bootstrap_servers", "localhost:9092")
        except Exception:
            pass

    kafka_ok = check_kafka_available(bootstrap)
    storage_ok = os.path.isdir("output")

    return SystemStatusResponse(
        status="operational",
        services=ServiceStatuses(
            kafka="healthy" if kafka_ok else "degraded",
            agents="healthy",
            api="healthy",
            storage="healthy" if storage_ok else "degraded",
        ),
        version="4.0 Enhanced",
        uptime_seconds=int(time.time() - _start_time),
    )
