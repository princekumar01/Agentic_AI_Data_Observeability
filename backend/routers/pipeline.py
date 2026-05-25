"""
backend/routers/pipeline.py
─────────────────────────────────────────────────────
All /pipeline/* endpoints.
Handles file upload, synthetic generation, preflight, run, status, reset.
Rate limited: 3 runs/minute/IP.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from backend.models.schemas import (
    ActiveRunResponse,
    GenerateSyntheticRequest,
    GenerateSyntheticResponse,
    KafkaHealthResponse,
    PipelineRunsResponse,
    PipelineStatusResponse,
    PipelineRunSummary,
    PreflightResponse,
    RecentRunsResponse,
    ResetPipelineRequest,
    ResetPipelineResponse,
    RunPipelineRequest,
    RunPipelineResponse,
    StageStatus,
    TestApiConnectionRequest,
    TestApiConnectionResponse,
    UploadResponse,
)
from backend.services import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# ─── Config loader ────────────────────────────────────────────────────────────

def _load_config() -> Dict:
    try:
        with open("config.yaml") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


# ─── In-memory pipeline state ─────────────────────────────────────────────────

STAGE_LABELS = [
    "Input Discovery",
    "Entry Validation",
    "Preprocessing",
    "PII/PHI Masking",
    "AI Agents",
    "Incident Report",
    "Awaiting Review",
]

_pipeline_runs: Dict[str, Dict[str, Any]] = {}
_runs_lock = threading.Lock()


def _new_run_state(run_id: str, input_mode: str, description: str = "") -> Dict:
    return {
        "run_id": run_id,
        "status": "running",
        "review_status": None,
        "input_mode": input_mode,
        "description": description,
        "rows": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "current_stage": STAGE_LABELS[0],
        "stage_index": 1,
        "total_stages": 7,
        "events_processed": 0,
        "stages": [
            {"num": i + 1, "label": lbl, "status": "pending", "duration_ms": None}
            for i, lbl in enumerate(STAGE_LABELS)
        ],
        "csv_path": None,
        "filename": None,
        "health_score": None,
        "health_label": None,
    }


def _set_stage(run_id: str, stage_idx: int, stage_status: str, duration_ms: Optional[int] = None) -> None:
    """0-indexed stage_idx."""
    with _runs_lock:
        run = _pipeline_runs.get(run_id)
        if not run:
            return
        run["stages"][stage_idx]["status"] = stage_status
        if duration_ms is not None:
            run["stages"][stage_idx]["duration_ms"] = duration_ms
        if stage_status == "active":
            run["current_stage"] = STAGE_LABELS[stage_idx]
            run["stage_index"] = stage_idx + 1


# ─── Rate limiter (3 runs/minute/IP) ──────────────────────────────────────────

_rate_buckets: Dict[str, List[float]] = defaultdict(list)
_rate_lock = threading.Lock()
RATE_LIMIT = 3
RATE_WINDOW = 60.0


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[client_ip]
        # Purge old entries
        _rate_buckets[client_ip] = [t for t in bucket if now - t < RATE_WINDOW]
        if len(_rate_buckets[client_ip]) >= RATE_LIMIT:
            return False
        _rate_buckets[client_ip].append(now)
        return True


# ─── Auth dependency ──────────────────────────────────────────────────────────

def _get_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[Dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        return auth_service.get_current_user(token)
    except ValueError:
        return None


def _require_auth(authorization: Optional[str] = Header(default=None)) -> Dict:
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ─── Background pipeline task ─────────────────────────────────────────────────

def _run_pipeline_bg(
    run_id: str,
    input_mode: str,
    window_size: int,
    inter_event_delay_ms: int,
    config: Dict,
) -> None:
    """Full pipeline execution: 7 stages."""
    import logging as _logging
    from backend.services.audit_service import AuditService
    from backend.services.validation_service import run_preflight
    from backend.services.preprocessing_service import run_preprocessing
    from backend.services.pii_service import mask_metrics_json, mask_etl_log, save_sanitized_metrics
    from backend.services.alert_service import write_alert
    from backend.agents.graph import run_agent_pipeline
    from backend.kafka.consumer import StreamProcessor
    from backend.kafka.producer import run_hospital_api_simulator
    from backend.services import streaming_state_service

    output_dir = os.path.join(
        config.get("output", {}).get("runs_directory", "output/runs"),
        run_id,
    )
    os.makedirs(output_dir, exist_ok=True)

    run_log = _logging.getLogger(f"pipeline.{run_id}")
    audit = AuditService(run_id=run_id, output_dir=output_dir)
    streaming_state = streaming_state_service.create_state(run_id, target_events=window_size)

    def mark(idx: int, s: str, ms: Optional[int] = None):
        _set_stage(run_id, idx, s, ms)

    def update_status(status_: str):
        with _runs_lock:
            r = _pipeline_runs.get(run_id)
            if r:
                r["status"] = status_

    t_total = time.time()

    try:
        # ── Stage 1: Input Discovery ──────────────────────────────────────────
        mark(0, "active")
        audit.log("input_discovery", "STAGE_START", {"stage": "input_discovery"})
        t0 = time.time()

        with _runs_lock:
            run = _pipeline_runs.get(run_id, {})
            csv_path = run.get("csv_path") or os.path.join(
                config.get("data", {}).get("csv_directory", "data/clinical"),
                config.get("data", {}).get("csv_filename", "clinical_trial_data.csv"),
            )
            filename = run.get("filename", "clinical_trial_data.csv")

        mark(0, "completed", int((time.time() - t0) * 1000))
        audit.log("input_discovery", "STAGE_COMPLETE", {"csv_path": csv_path, "mode": input_mode})

        # ── Stage 2: Entry Validation ──────────────────────────────────────────
        mark(1, "active")
        t0 = time.time()
        audit.log("entry_validation", "STAGE_START", {})

        preflight = run_preflight(csv_path, run_id, config, output_dir)
        if not preflight["passed"]:
            write_alert(
                severity="CRITICAL",
                message=f"Pre-ingest validation failed: {len(preflight['hard_blocks'])} hard block(s)",
                run_id=run_id,
                source="validation_service",
            )
            mark(1, "failed", int((time.time() - t0) * 1000))
            update_status("failed")
            audit.finalize("failed")
            return

        mark(1, "completed", int((time.time() - t0) * 1000))
        audit.log("entry_validation", "STAGE_COMPLETE", {"passed": True, "rows": preflight["row_count"]})
        with _runs_lock:
            r = _pipeline_runs.get(run_id)
            if r:
                r["rows"] = preflight["row_count"]

        # ── Stage 3: Preprocessing (Kafka) ────────────────────────────────────
        mark(2, "active")
        t0 = time.time()
        audit.log("preprocessing", "STAGE_START", {"window_size": window_size})

        # Create a minimal ETL logger for the consumer stage
        etl_log_path = os.path.join(output_dir, "etl_run.log")
        etl_logger = _logging.getLogger(f"etl_{run_id}")
        etl_logger.handlers.clear()
        etl_logger.setLevel(_logging.DEBUG)
        fh = _logging.FileHandler(etl_log_path, mode="w", encoding="utf-8")
        fh.setFormatter(_logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        etl_logger.addHandler(fh)

        # Start producer in background thread
        config["kafka"]["window_threshold"] = window_size
        producer_errors: List[str] = []

        def run_producer() -> None:
            try:
                run_hospital_api_simulator(
                    csv_path=csv_path,
                    run_id=run_id,
                    config=config,
                    logger_=etl_logger,
                    audit_service=audit,
                    mode=input_mode if input_mode in ("csv", "synthetic", "synthea", "api") else "csv",
                    kafka_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS",
                                                config.get("kafka", {}).get("bootstrap_servers", "localhost:9092")),
                    delay_ms=inter_event_delay_ms,
                    topic=config.get("kafka", {}).get("topic", "clinical_trial_events"),
                    streaming_state=streaming_state,
                )
            except Exception as exc:
                producer_errors.append(str(exc))
                etl_logger.error(f"[Producer] Fatal error: {exc}", exc_info=True)

        producer_thread = threading.Thread(
            target=run_producer,
            daemon=True,
        )
        producer_thread.start()

        # Start consumer
        consumer = StreamProcessor(
            run_id=run_id,
            config=config,
            etl_logger=etl_logger,
            audit_service=audit,
            output_dir=output_dir,
            streaming_state=streaming_state,
        )
        event_buffer = consumer.consume_and_process()
        streaming_metadata = consumer.get_streaming_metadata()

        producer_thread.join(timeout=30)
        streaming_state.set_producer_done()

        if producer_errors or not event_buffer:
            reason = producer_errors[0] if producer_errors else "No events were consumed from Kafka"
            write_alert(
                severity="CRITICAL",
                message=f"Preprocessing failed: {reason}",
                run_id=run_id,
                source="preprocessing",
            )
            mark(2, "failed", int((time.time() - t0) * 1000))
            update_status("failed")
            audit.log("preprocessing", "STAGE_FAILED", {"reason": reason})
            audit.finalize("failed")
            return

        with _runs_lock:
            r = _pipeline_runs.get(run_id)
            if r:
                r["events_processed"] = len(event_buffer)

        # Close ETL logger
        for handler in list(etl_logger.handlers):
            handler.flush()
            handler.close()
            etl_logger.removeHandler(handler)

        mark(2, "completed", int((time.time() - t0) * 1000))
        audit.log("preprocessing", "STAGE_COMPLETE", {"events_collected": len(event_buffer)})

        # Run rolling metrics on event buffer
        from backend.services.preprocessing_service import run_preprocessing
        rolling_metrics = run_preprocessing(
            event_buffer=event_buffer,
            streaming_metadata=streaming_metadata,
            run_id=run_id,
            config=config,
            output_dir=output_dir,
        )

        # ── Stage 4: PII/PHI Masking ──────────────────────────────────────────
        mark(3, "active")
        t0 = time.time()
        audit.log("pii_masking", "STAGE_START", {})

        try:
            masked_metrics = mask_metrics_json(rolling_metrics)
        except RuntimeError as exc:
            run_log.error(f"PII masking failed: {exc}")
            write_alert(severity="CRITICAL", message=str(exc), run_id=run_id, source="pii_service")
            mark(3, "failed", int((time.time() - t0) * 1000))
            update_status("failed")
            audit.finalize("failed")
            return

        sanitized_metrics_path = save_sanitized_metrics(masked_metrics, output_dir)
        sanitized_log_path = mask_etl_log(etl_log_path, output_dir)

        with open(sanitized_log_path, encoding="utf-8") as fh_:
            sanitized_log_text = fh_.read()

        mark(3, "completed", int((time.time() - t0) * 1000))
        audit.log("pii_masking", "STAGE_COMPLETE", {"entities_masked": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]})

        # ── Stage 5: AI Agents ─────────────────────────────────────────────────
        mark(4, "active")
        t0 = time.time()
        audit.log("ai_agents", "STAGE_START", {})

        # Update agent statuses for streaming view
        streaming_state.update_agents_status([
            {"name": a, "status": "PENDING", "last_run": None, "confidence": None, "findings": None}
            for a in ["data_quality_agent", "log_analysis_agent", "rca_agent", "recommendation_agent", "compliance_agent"]
        ])

        agent_state = run_agent_pipeline(
            run_id=run_id,
            sanitized_metrics=masked_metrics,
            sanitized_log_text=sanitized_log_text,
            streaming_metadata=streaming_metadata,
            output_dir=output_dir,
        )

        if agent_state.get("error"):
            write_alert(
                severity="CRITICAL",
                message=f"Agent pipeline error: {agent_state['error']}",
                run_id=run_id,
                source="agent_graph",
            )
            mark(4, "failed", int((time.time() - t0) * 1000))
            update_status("failed")
            audit.finalize("failed")
            return

        # Update agent statuses post-completion
        conf_path = os.path.join(output_dir, "agent_confidence.json")
        conf_data: Dict = {}
        if os.path.exists(conf_path):
            try:
                with open(conf_path) as fc:
                    conf_data = json.load(fc)
            except Exception:
                pass

        now_iso = datetime.now(timezone.utc).isoformat()
        streaming_state.update_agents_status([
            {
                "name": a,
                "status": "COMPLETED",
                "last_run": now_iso,
                "confidence": conf_data.get(a, 0),
                "findings": None,
            }
            for a in ["data_quality_agent", "log_analysis_agent", "rca_agent", "recommendation_agent", "compliance_agent"]
        ])

        mark(4, "completed", int((time.time() - t0) * 1000))
        audit.log("ai_agents", "STAGE_COMPLETE", {"agents_completed": 5})

        # ── Stage 6: Incident Report ───────────────────────────────────────────
        mark(5, "active")
        t0 = time.time()
        audit.log("incident_report", "STAGE_START", {})

        # incident_report_draft.md already written by aggregator node
        draft_path = os.path.join(output_dir, "incident_report_draft.md")
        if not os.path.exists(draft_path):
            run_log.warning("incident_report_draft.md not found — creating placeholder")
            with open(draft_path, "w") as fp:
                fp.write(f"# Incident Report Draft\nRun: {run_id}\nGenerated: {now_iso}\n")

        mark(5, "completed", int((time.time() - t0) * 1000))
        audit.log("incident_report", "STAGE_COMPLETE", {"draft_path": draft_path})

        # ── Stage 7: Awaiting Review ───────────────────────────────────────────
        mark(6, "active")
        audit.log("awaiting_review", "STAGE_START", {})

        with _runs_lock:
            r = _pipeline_runs.get(run_id)
            if r:
                r["status"] = "pending_review"
                r["review_status"] = "pending"
                r["completed_at"] = datetime.now(timezone.utc).isoformat()
                r["health_score"] = rolling_metrics.get("health_score")
                r["health_label"] = rolling_metrics.get("health_label")
                r["stages"][6]["status"] = "completed"
                r["current_stage"] = "Awaiting Review"

        audit.finalize("pending_review")
        run_log.info(f"[pipeline] Run {run_id} completed — pending review")

    except Exception as exc:
        run_log.error(f"[pipeline] Unhandled error in run {run_id}: {exc}", exc_info=True)
        update_status("failed")
        try:
            audit.finalize("failed")
        except Exception:
            pass


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=PipelineRunsResponse)
def list_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    user: Dict = Depends(_require_auth),
):
    with _runs_lock:
        all_runs = sorted(
            _pipeline_runs.values(),
            key=lambda r: r.get("started_at", ""),
            reverse=True,
        )
    total = len(all_runs)
    start = (page - 1) * limit
    page_runs = all_runs[start : start + limit]
    return PipelineRunsResponse(
        runs=[_to_summary(r) for r in page_runs],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/runs/recent", response_model=RecentRunsResponse)
def recent_runs(limit: int = Query(5, ge=1, le=50)):
    with _runs_lock:
        all_runs = sorted(
            _pipeline_runs.values(),
            key=lambda r: r.get("started_at", ""),
            reverse=True,
        )[:limit]
    return RecentRunsResponse(
        runs=[_to_summary(r) for r in all_runs],
        total=len(all_runs),
    )


@router.get("/runs/active", response_model=ActiveRunResponse)
def active_run(user: Dict = Depends(_require_auth)):
    with _runs_lock:
        for run in reversed(list(_pipeline_runs.values())):
            if run["status"] in ("running", "pending_review"):
                return ActiveRunResponse(
                    run_id=run["run_id"],
                    status=run["status"],
                    review_status=run.get("review_status"),
                    started_at=run.get("started_at"),
                    completed_at=run.get("completed_at"),
                )
    return ActiveRunResponse(run_id=None, status="idle")


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    run_id: Optional[str] = Form(default=None),
    user: Dict = Depends(_require_auth),
):
    from backend.services.input_service import save_uploaded_file

    config = _load_config()
    uploads_dir = config.get("data", {}).get("uploads_directory", "data/uploads")
    run_id = run_id or str(uuid.uuid4())

    file_bytes = await file.read()
    saved_path, info = save_uploaded_file(file_bytes, file.filename or "upload.csv", run_id, uploads_dir)

    # Cache csv_path for this run
    with _runs_lock:
        if run_id not in _pipeline_runs:
            _pipeline_runs[run_id] = _new_run_state(run_id, "csv")
        _pipeline_runs[run_id]["csv_path"] = saved_path
        _pipeline_runs[run_id]["filename"] = file.filename

    return UploadResponse(**info)


@router.post("/generate-synthetic", response_model=GenerateSyntheticResponse)
def generate_synthetic(
    body: GenerateSyntheticRequest,
    user: Dict = Depends(_require_auth),
):
    from scripts.generate_synthetic_data import generate_dataset

    config = _load_config()
    run_id = str(uuid.uuid4())
    records = generate_dataset(
        scenario=body.scenario,
        rows=body.rows,
        null_rate=body.null_rate,
        outlier_pct=body.outlier_pct,
        date_drift_days=body.date_drift_days,
        duplicate_rate=body.duplicate_rate,
    )

    import pandas as pd
    df = pd.DataFrame(records)
    csv_dir = config.get("data", {}).get("uploads_directory", "data/uploads")
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, f"{run_id}_synthetic.csv")
    df.to_csv(csv_path, index=False)

    sev_dist = df["severity"].value_counts().to_dict() if "severity" in df.columns else {}
    null_avg = float(df.isnull().mean().mean())
    outlier_preview = body.outlier_pct

    with _runs_lock:
        _pipeline_runs[run_id] = _new_run_state(run_id, "synthetic")
        _pipeline_runs[run_id]["csv_path"] = csv_path
        _pipeline_runs[run_id]["filename"] = f"synthetic_{body.scenario}.csv"

    return GenerateSyntheticResponse(
        run_id=run_id,
        scenario=body.scenario,
        rows_generated=len(records),
        columns=list(df.columns),
        saved_to=csv_path,
        generated_at=datetime.now(timezone.utc).isoformat(),
        preview={"null_rate_avg": round(null_avg, 4), "outlier_pct": outlier_preview, "severity_distribution": sev_dist},
    )


@router.post("/test-api-connection", response_model=TestApiConnectionResponse)
def test_api_connection(
    body: TestApiConnectionRequest,
    user: Dict = Depends(_require_auth),
):
    from backend.services.input_service import test_api_connection

    result = test_api_connection(
        url=body.url,
        auth_type=body.auth_type,
        token=body.token,
        max_records=body.max_records_per_poll,
    )
    return TestApiConnectionResponse(**result)


@router.post("/preflight/{run_id}", response_model=PreflightResponse)
def run_preflight_endpoint(
    run_id: str,
    user: Dict = Depends(_require_auth),
):
    from backend.services.validation_service import run_preflight

    config = _load_config()
    output_dir = os.path.join(
        config.get("output", {}).get("runs_directory", "output/runs"), run_id
    )
    os.makedirs(output_dir, exist_ok=True)

    with _runs_lock:
        run = _pipeline_runs.get(run_id)
    csv_path = (run or {}).get("csv_path") or os.path.join(
        config.get("data", {}).get("csv_directory", "data/clinical"),
        config.get("data", {}).get("csv_filename", "clinical_trial_data.csv"),
    )

    report = run_preflight(csv_path, run_id, config, output_dir)
    return PreflightResponse(**report)


@router.get("/preflight/{run_id}", response_model=PreflightResponse)
def get_preflight(run_id: str, user: Dict = Depends(_require_auth)):
    config = _load_config()
    output_dir = os.path.join(
        config.get("output", {}).get("runs_directory", "output/runs"), run_id
    )
    path = os.path.join(output_dir, "preflight_report.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Preflight report not found")
    with open(path) as fh:
        data = json.load(fh)
    return PreflightResponse(**data)


@router.post("/run", response_model=RunPipelineResponse, status_code=status.HTTP_202_ACCEPTED)
def run_pipeline(
    request: Request,
    body: RunPipelineRequest,
    background_tasks: BackgroundTasks,
    user: Dict = Depends(_require_auth),
    x_api_key: Optional[str] = Header(default=None),
):
    # Validate API key
    expected_key = os.environ.get("PIPELINE_API_KEY", "")
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid or missing X-API-Key header")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many requests — wait before retrying", "retry_after_seconds": 60},
        )

    run_id = body.run_id
    config = _load_config()
    logger.info(
        "[pipeline] Run request received | run_id=%s mode=%s window_size=%s delay_ms=%s",
        run_id,
        body.input_mode,
        body.window_size,
        body.inter_event_delay_ms,
    )
    if body.input_mode == "api":
        if not body.api_url:
            raise HTTPException(status_code=400, detail="API URL is required for External API runs")
        logger.info("[pipeline] External API mode configured | run_id=%s url=%s", run_id, body.api_url)
        config["external_api"] = {
            "url": body.api_url,
            "auth_type": body.api_auth_type,
            "token": body.api_token,
            "max_records_per_poll": body.api_max_records_per_poll,
        }

    with _runs_lock:
        if run_id not in _pipeline_runs:
            _pipeline_runs[run_id] = _new_run_state(run_id, body.input_mode, body.description or "")
        else:
            # Update existing run state
            _pipeline_runs[run_id]["status"] = "running"
            _pipeline_runs[run_id]["input_mode"] = body.input_mode
            for s in _pipeline_runs[run_id]["stages"]:
                s["status"] = "pending"
                s["duration_ms"] = None

    background_tasks.add_task(
        _run_pipeline_bg,
        run_id=run_id,
        input_mode=body.input_mode,
        window_size=body.window_size,
        inter_event_delay_ms=body.inter_event_delay_ms,
        config=config,
    )

    return RunPipelineResponse(
        run_id=run_id,
        status="running",
        started_at=_pipeline_runs[run_id]["started_at"],
        current_stage=STAGE_LABELS[0],
        stage_index=1,
        total_stages=7,
    )


@router.get("/status/{run_id}", response_model=PipelineStatusResponse)
def pipeline_status(run_id: str, user: Dict = Depends(_require_auth)):
    with _runs_lock:
        run = _pipeline_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return PipelineStatusResponse(
        run_id=run["run_id"],
        status=run["status"],
        current_stage=run["current_stage"],
        stage_index=run["stage_index"],
        total_stages=run["total_stages"],
        stages=[StageStatus(**s) for s in run["stages"]],
        events_processed=run.get("events_processed", 0),
        started_at=run["started_at"],
    )


@router.post("/reset", response_model=ResetPipelineResponse)
def reset_pipeline(body: ResetPipelineRequest, user: Dict = Depends(_require_auth)):
    with _runs_lock:
        run = _pipeline_runs.get(body.run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        for s in run["stages"]:
            s["status"] = "pending"
            s["duration_ms"] = None
        run["stage_index"] = 1
        run["current_stage"] = STAGE_LABELS[0]
    return ResetPipelineResponse(success=True, message="Pipeline state reset successfully")


@router.get("/kafka-health", response_model=KafkaHealthResponse)
def kafka_health():
    from backend.kafka.topics import check_kafka_available
    config = _load_config()
    servers = os.environ.get(
        "KAFKA_BOOTSTRAP_SERVERS",
        config.get("kafka", {}).get("bootstrap_servers", "localhost:9092"),
    )
    topic = config.get("kafka", {}).get("topic", "clinical_trial_events")
    ok = check_kafka_available(servers)
    return KafkaHealthResponse(
        kafka_available=ok,
        bootstrap_servers=servers,
        topic=topic,
        message="Kafka is healthy" if ok else "Kafka not reachable",
    )


# ─── Helper ───────────────────────────────────────────────────────────────────

def _to_summary(r: Dict) -> PipelineRunSummary:
    return PipelineRunSummary(
        run_id=r["run_id"],
        input_mode=r.get("input_mode", "csv"),
        rows=r.get("rows", 0),
        status=r.get("status", "unknown"),
        started_at=r.get("started_at", ""),
        completed_at=r.get("completed_at"),
        description=r.get("description"),
    )


# ─── Expose _pipeline_runs for other routers ─────────────────────────────────

def get_pipeline_runs() -> Dict[str, Dict]:
    return _pipeline_runs
