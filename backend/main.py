"""
main.py
FastAPI application entry point.
Run with: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import pipeline, review, dashboard

# ── Ensure output directory exists ──────────────────────────────────────────
def _ensure_dirs():
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        runs_dir = config.get("output", {}).get("runs_directory", "output/runs")
        os.makedirs(runs_dir, exist_ok=True)
    except Exception:
        os.makedirs("output/runs", exist_ok=True)

_ensure_dirs()

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Clinical Trial AI Data Observability API",
    description=(
        "Agentic AI-powered Data Observability System for Clinical Trials. "
        "Monitors data quality across 5 observability pillars with full audit trail "
        "and human-in-the-loop review before regulatory reporting."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(review.router, prefix="/review", tags=["HITL Review"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Clinical Trial AI Data Observability API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
