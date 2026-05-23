"""
backend/main.py
─────────────────────────────────────────────────────
FastAPI application entry point.

Startup:
  1. Load .env
  2. Create output directories
  3. Ensure Kafka topic exists (non-fatal)
  4. Mount all routers

CORS: allow all origins in local POC (restrict in production).

Run:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
import os

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ─── Load env early so llm_config.py can read OPENAI_API_KEY ─────────────────
load_dotenv()

# ─── Routers ──────────────────────────────────────────────────────────────────
from backend.routers.auth import router as auth_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.streaming import router as streaming_router
from backend.routers.review import router as review_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.alerts import router as alerts_router
from backend.routers.audit import router as audit_router
from backend.routers.system import router as system_router

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Clinical Trial AI Observability API",
    description=(
        "Agentic AI Data Observability for Clinical Trials "
        "with Real-Time Kafka Streaming, LangGraph orchestration, "
        "and Human-in-the-Loop review. "
        "FDA 21 CFR Part 11 / ICH E6 GCP / HIPAA compliant."
    ),
    version="6.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS — allow all origins for local POC ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event() -> None:
    logger.info("=" * 60)
    logger.info("Clinical Trial AI Observability API v6.0 — STARTING")
    logger.info("=" * 60)

    # Ensure output directories exist
    for directory in [
        "output/runs",
        "output/alerts",
        "output/regression",
        "data/clinical",
        "data/uploads",
        "config",
    ]:
        os.makedirs(directory, exist_ok=True)

    # Load config
    cfg: dict = {}
    try:
        with open("config.yaml") as fh:
            cfg = yaml.safe_load(fh) or {}
        logger.info("config.yaml loaded successfully")
    except FileNotFoundError:
        logger.warning("config.yaml not found — using defaults")

    # Ensure Kafka topic (non-fatal)
    kafka_cfg = cfg.get("kafka", {})
    bootstrap = os.environ.get(
        "KAFKA_BOOTSTRAP_SERVERS",
        kafka_cfg.get("bootstrap_servers", "localhost:9092"),
    )
    topic = kafka_cfg.get("topic", "clinical_trial_events")
    try:
        from backend.kafka.topics import ensure_topic_exists
        ensure_topic_exists(bootstrap, topic)
        logger.info(f"Kafka topic '{topic}' ensured on {bootstrap}")
    except Exception as exc:
        logger.warning(f"Kafka topic creation skipped (Kafka may be unavailable): {exc}")

    logger.info("Startup complete — API is ready")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Clinical Trial AI Observability API — shutting down")


# ─── Register routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(pipeline_router)
app.include_router(streaming_router)
app.include_router(review_router)
app.include_router(dashboard_router)
app.include_router(alerts_router)
app.include_router(audit_router)
app.include_router(system_router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "version": "6.0.0"}


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
def root():
    return {
        "name": "Clinical Trial AI Observability API",
        "version": "6.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
