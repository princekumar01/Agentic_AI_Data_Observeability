"""
backend/services/audit_service.py
─────────────────────────────────────────────────────
Immutable append-only audit trail.  Records NEVER updated or deleted.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


class AuditService:
    """Thread-safe, append-only audit trail written to audit_trail.json."""

    def __init__(self, run_id: str, output_dir: str) -> None:
        self.run_id = run_id
        self.output_dir = output_dir
        self._path = os.path.join(output_dir, "audit_trail.json")
        self._lock = Lock()
        self._counter = 0

        # Initialise the file
        initial = {
            "run_id": run_id,
            "pipeline_started_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_completed_at": None,
            "pipeline_status": "running",
            "entries": [],
            "hitl_decision": {
                "decision": None,
                "reviewer_id": None,
                "notes": None,
                "decided_at": None,
                "escalated": False,
            },
            "data_fingerprint": None,
        }
        os.makedirs(output_dir, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(initial, fh, indent=2)

    # ─── Public API ───────────────────────────────────────────────────────────

    def log(
        self,
        stage: str,
        event_type: str,
        data: Dict[str, Any],
        agent: Optional[str] = None,
    ) -> None:
        """Append one immutable entry.  Written to disk immediately."""
        with self._lock:
            self._counter += 1
            entry = {
                "entry_id": self._counter,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "event_type": event_type,
                "agent": agent,
                "data": data,
            }
            trail = self._read()
            trail["entries"].append(entry)
            self._write(trail)

    def finalize(self, status: str) -> None:
        """Set pipeline_completed_at and pipeline_status."""
        with self._lock:
            trail = self._read()
            trail["pipeline_completed_at"] = datetime.now(timezone.utc).isoformat()
            trail["pipeline_status"] = status
            self._write(trail)

    def record_hitl_decision(
        self,
        decision: str,
        reviewer_id: str,
        notes: Optional[str],
        escalated: bool = False,
    ) -> None:
        """Update the HITL decision block and emit an audit entry."""
        with self._lock:
            trail = self._read()
            trail["hitl_decision"] = {
                "decision": decision,
                "reviewer_id": reviewer_id,
                "notes": notes,
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "escalated": escalated,
            }
            self._write(trail)

        self.log(
            stage="human_review",
            event_type="HITL_DECISION",
            data={"decision": decision, "reviewer_id": reviewer_id, "notes": notes},
        )

    def set_data_fingerprint(self, fingerprint: Dict[str, Any]) -> None:
        with self._lock:
            trail = self._read()
            trail["data_fingerprint"] = fingerprint
            self._write(trail)

    def read_all(self) -> Dict[str, Any]:
        """Return the full audit trail dict (caller must not mutate)."""
        with self._lock:
            return self._read()

    # ─── Private ──────────────────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        with open(self._path, encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, trail: Dict[str, Any]) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(trail, fh, indent=2)
        os.replace(tmp, self._path)
