"""
audit_service.py
File-based audit trail writer. One JSON file per pipeline execution.
Stored at: output/runs/{run_id}/audit_trail.json

Design: Append-only. Written after every event so partial runs are preserved.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional


class AuditService:
    """
    Manages the audit trail for a single pipeline run.
    Each call to log() immediately appends to the JSON file on disk.
    """

    def __init__(self, run_id: str, output_dir: str):
        self.run_id = run_id
        self.audit_path = os.path.join(output_dir, "audit_trail.json")
        self.entry_counter = 0

        initial_record = {
            "run_id": run_id,
            "pipeline_started_at": self._now(),
            "pipeline_completed_at": None,
            "pipeline_status": "running",
            "entries": [],
            "hitl_decision": {
                "decision": None,
                "reviewer_id": None,
                "reviewer_notes": None,
                "decided_at": None,
            },
        }
        self._write(initial_record)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def log(
        self,
        stage: str,
        event_type: str,
        data: dict,
        agent: Optional[str] = None,
    ) -> None:
        """Append one audit entry to the JSON file."""
        self.entry_counter += 1
        entry = {
            "entry_id": self.entry_counter,
            "timestamp": self._now(),
            "stage": stage,
            "event_type": event_type,
            "agent": agent,
            "data": data,
        }
        record = self._read()
        record["entries"].append(entry)
        self._write(record)

    def finalize(self, status: str) -> None:
        """Mark the pipeline as completed/failed with a final status."""
        record = self._read()
        record["pipeline_completed_at"] = self._now()
        record["pipeline_status"] = status
        self._write(record)

    def record_hitl_decision(
        self, decision: str, reviewer_id: str, notes: str
    ) -> None:
        """Record the human reviewer's approve/reject decision."""
        record = self._read()
        record["hitl_decision"] = {
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reviewer_notes": notes,
            "decided_at": self._now(),
        }
        record["pipeline_status"] = decision  # "approved" or "rejected"
        record["pipeline_completed_at"] = self._now()
        self._write(record)

        # Also append as a regular audit entry
        self.log(
            stage="hitl_review",
            event_type="hitl_decision",
            data={
                "decision": decision,
                "reviewer_id": reviewer_id,
                "notes": notes,
            },
        )

    def get_record(self) -> dict:
        """Return the full audit record dict."""
        return self._read()

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _read(self) -> dict:
        with open(self.audit_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, record: dict) -> None:
        with open(self.audit_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Standalone helper — load an audit file by run_id
# ─────────────────────────────────────────────────────────────────────────────

def load_audit(run_id: str, runs_dir: str) -> Optional[dict]:
    """Load and return the audit trail JSON for a given run_id."""
    path = os.path.join(runs_dir, run_id, "audit_trail.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
