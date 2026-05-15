"""
pipeline.py
FastAPI router for pipeline trigger and status endpoints.

POST /pipeline/run      — trigger the full pipeline as a background task
GET  /pipeline/status/{run_id} — poll pipeline progress
GET  /pipeline/history  — list all previous runs
"""

import os
import json
import uuid
import traceback
from datetime import datetime, timezone

import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.models.schemas import RunTriggerResponse, PipelineStatus, RunHistoryItem
from backend.services.input_service import discover_csv
from backend.services.validation_service import validate_entry
from backend.services.preprocessing_service import run_preprocessing
from backend.services.pii_service import mask_metrics_json, mask_etl_log, save_sanitized_metrics
from backend.services.audit_service import AuditService
from backend.services.dashboard_service import list_runs
from backend.agents.graph import run_agent_pipeline

router = APIRouter()

# ── In-memory run progress tracker ──────────────────────────────────────────
# {run_id: {"status": str, "current_stage": str, "progress_pct": int,
#            "errors": list, "warnings": list}}
_run_progress: dict[str, dict] = {}
_active_run_id: str | None = None  # Only one run at a time for POC


def _load_config() -> dict:
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def _update_progress(run_id: str, status: str, stage: str, pct: int,
                     errors: list = None, warnings: list = None):
    _run_progress[run_id] = {
        "status": status,
        "current_stage": stage,
        "progress_pct": pct,
        "errors": errors or [],
        "warnings": warnings or [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunTriggerResponse)
async def trigger_pipeline(background_tasks: BackgroundTasks):
    global _active_run_id

    if _active_run_id and _run_progress.get(_active_run_id, {}).get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run ({_active_run_id}) is already in progress. "
                   f"Please wait for it to complete.",
        )

    run_id = str(uuid.uuid4())
    _active_run_id = run_id
    _update_progress(run_id, "running", "initializing", 0)

    background_tasks.add_task(_execute_pipeline, run_id)

    return RunTriggerResponse(
        run_id=run_id,
        status="started",
        message=f"Pipeline execution started. Poll /pipeline/status/{run_id} for progress.",
    )


@router.get("/status/{run_id}", response_model=PipelineStatus)
async def get_pipeline_status(run_id: str):
    if run_id not in _run_progress:
        raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found.")

    prog = _run_progress[run_id]
    return PipelineStatus(
        run_id=run_id,
        status=prog["status"],
        current_stage=prog["current_stage"],
        progress_pct=prog["progress_pct"],
        errors=prog["errors"],
        warnings=prog["warnings"],
    )


@router.get("/history")
async def get_run_history():
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]
    return list_runs(runs_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline execution
# ─────────────────────────────────────────────────────────────────────────────

def _execute_pipeline(run_id: str):
    """
    Full pipeline execution — runs in a FastAPI BackgroundTask.
    Writes all artifacts to output/runs/{run_id}/.
    """
    config = _load_config()
    runs_dir = config["output"]["runs_directory"]
    output_dir = os.path.join(runs_dir, run_id)
    os.makedirs(output_dir, exist_ok=True)

    audit = AuditService(run_id, output_dir)

    try:
        # ── Stage 1: Input Discovery ─────────────────────────────────────────
        _update_progress(run_id, "running", "input_discovery", 5)
        audit.log("input_discovery", "stage_start", {"stage_name": "input_discovery"})

        csv_info = discover_csv(config)

        audit.log("input_discovery", "stage_complete", {
            "stage_name": "input_discovery",
            "csv_path": csv_info["csv_path"],
            "file_size_bytes": csv_info["file_size_bytes"],
        })

        # ── Stage 2: Entry Validation ────────────────────────────────────────
        _update_progress(run_id, "running", "entry_validation", 15)
        audit.log("entry_validation", "stage_start", {"stage_name": "entry_validation"})

        validation_result = validate_entry(
            csv_path=csv_info["csv_path"],
            file_modified_at=csv_info["file_modified_at"],
            config=config,
        )

        audit.log("entry_validation", "stage_complete", {
            "stage_name": "entry_validation",
            "passed": validation_result["passed"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
        })

        if not validation_result["passed"]:
            _update_progress(
                run_id, "validation_failed", "entry_validation", 15,
                errors=validation_result["errors"],
                warnings=validation_result["warnings"],
            )
            audit.finalize("validation_failed")
            return

        # ── Stage 3: Preprocessing ───────────────────────────────────────────
        _update_progress(run_id, "running", "preprocessing", 30,
                         warnings=validation_result["warnings"])
        audit.log("preprocessing", "stage_start", {"stage_name": "preprocessing"})

        preproc_result = run_preprocessing(
            csv_path=csv_info["csv_path"],
            run_id=run_id,
            config=config,
            output_dir=output_dir,
        )

        raw_metrics = preproc_result["metrics"]
        log_path = preproc_result["log_path"]

        # Save raw metrics
        raw_metrics_path = os.path.join(output_dir, "metrics.json")
        with open(raw_metrics_path, "w", encoding="utf-8") as f:
            json.dump(raw_metrics, f, indent=2, default=str)

        audit.log("preprocessing", "stage_complete", {
            "stage_name": "preprocessing",
            "health_score": raw_metrics.get("overall_health_score"),
            "anomaly_count": raw_metrics.get("anomaly_count"),
            "log_path": log_path,
        })

        # ── Stage 4: PII/PHI Masking ─────────────────────────────────────────
        _update_progress(run_id, "running", "pii_masking", 50,
                         warnings=validation_result["warnings"])
        audit.log("pii_masking", "stage_start", {"stage_name": "pii_masking"})

        try:
            sanitized_metrics = mask_metrics_json(raw_metrics)
            sanitized_metrics_path = save_sanitized_metrics(sanitized_metrics, output_dir)
            sanitized_log_path = mask_etl_log(log_path, output_dir)

            with open(sanitized_log_path, "r", encoding="utf-8") as f:
                sanitized_log_text = f.read()

        except RuntimeError as pii_exc:
            # PHI safety is non-negotiable — halt the pipeline
            error_msg = str(pii_exc)
            _update_progress(run_id, "error", "pii_masking", 50, errors=[error_msg])
            audit.log("pii_masking", "stage_error", {
                "stage_name": "pii_masking",
                "error": error_msg,
            })
            audit.finalize("error")
            return

        audit.log("pii_masking", "stage_complete", {
            "stage_name": "pii_masking",
            "sanitized_metrics_path": sanitized_metrics_path,
            "sanitized_log_path": sanitized_log_path,
        })

        # ── Stage 5: Agentic AI Layer ────────────────────────────────────────
        _update_progress(run_id, "running", "agent_pipeline", 60,
                         warnings=validation_result["warnings"])
        audit.log("agent_pipeline", "stage_start", {"stage_name": "agent_pipeline"})

        final_state = run_agent_pipeline(
            run_id=run_id,
            sanitized_metrics=sanitized_metrics,
            sanitized_log_text=sanitized_log_text,
        )

        # Flush all agent audit entries accumulated in LangGraph state
        for agent_entry in final_state.get("audit_entries", []):
            stage = agent_entry.get("stage", "agent_pipeline")
            event_type = agent_entry.get("event_type", "agent_event")
            agent = agent_entry.get("agent")
            data = agent_entry.get("data", {})
            audit.log(stage, event_type, data, agent=agent)

        # ── Stage 6: Save Incident Report ────────────────────────────────────
        _update_progress(run_id, "running", "saving_report", 90,
                         warnings=validation_result["warnings"])

        incident_report = final_state.get("incident_report", "")
        # Note: incident_report.md is only written after HITL approval
        # Store draft in audit for now
        audit.log("incident_report", "stage_complete", {
            "stage_name": "incident_report",
            "report_length": len(incident_report),
            "compliance_status": _extract_compliance_status(
                final_state.get("compliance_review", "")
            ),
        })

        # Save draft report separately (not the final approved one)
        draft_path = os.path.join(output_dir, "incident_report_draft.md")
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(incident_report)

        # ── Stage 7: Await HITL Review ───────────────────────────────────────
        _update_progress(run_id, "pending_review", "awaiting_human_review", 95,
                         warnings=validation_result["warnings"])
        audit.finalize("pending_review")

    except FileNotFoundError as exc:
        error_msg = str(exc)
        _update_progress(run_id, "error", "input_discovery", 5, errors=[error_msg])
        audit.log("pipeline", "stage_error", {"error": error_msg, "traceback": ""})
        audit.finalize("error")

    except Exception as exc:
        error_msg = str(exc)
        tb = traceback.format_exc()
        _update_progress(run_id, "error", "unknown", 0, errors=[error_msg])
        audit.log("pipeline", "stage_error", {
            "error": error_msg,
            "traceback": tb,
        })
        audit.finalize("error")


def _extract_compliance_status(compliance_text: str) -> str:
    """Extract the compliance status from the compliance agent's response."""
    for line in compliance_text.splitlines():
        if "COMPLIANCE STATUS:" in line:
            return line.split("COMPLIANCE STATUS:")[-1].strip()
    return "UNKNOWN"
