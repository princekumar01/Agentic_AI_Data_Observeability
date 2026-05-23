"""
backend/services/streaming_state_service.py
─────────────────────────────────────────────────────
In-memory streaming state updated by producer/consumer threads
and read by /streaming/* endpoints.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


@dataclass
class StreamingState:
    run_id: str
    started_at: float = field(default_factory=time.time)

    # Producer
    events_published: int = 0
    producer_errors: int = 0
    last_published_at: Optional[str] = None
    producer_status: str = "IDLE"

    # Consumer
    events_received: int = 0
    events_valid: int = 0
    events_invalid: int = 0
    consumer_lag_samples: List[int] = field(default_factory=list)
    consumer_errors: int = 0
    last_consumed_at: Optional[str] = None
    consumer_status: str = "IDLE"

    # History buffers (kept as plain lists for JSON-serialisable reads)
    lag_history: List[Dict] = field(default_factory=list)
    throughput_history: List[Dict] = field(default_factory=list)
    recent_events: Deque = field(default_factory=lambda: deque(maxlen=20))

    # AI findings and agent statuses
    ai_findings: List[Dict] = field(default_factory=list)
    agents_status: List[Dict] = field(default_factory=list)

    # Window
    window_status: Dict = field(default_factory=dict)

    # Targets
    target_events: int = 500

    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    # ── Update helpers (called by producer / consumer threads) ────────────────

    def record_published(self, event: Dict) -> None:
        with self._lock:
            self.events_published += 1
            self.last_published_at = datetime.now(timezone.utc).isoformat()
            self.producer_status = "RUNNING"
            now_iso = self.last_published_at
            self.recent_events.append({
                "event_id": event.get("event_id", "?"),
                "event_type": "patient_record",
                "time": now_iso,
                "status": "published",
            })
            # Throughput: approximate events/sec
            elapsed = max(1.0, time.time() - self.started_at)
            rate = round(self.events_published / elapsed, 2)
            self.throughput_history.append({"timestamp": now_iso, "events_per_sec": rate})
            # Keep last 300 data points
            if len(self.throughput_history) > 300:
                self.throughput_history = self.throughput_history[-300:]

    def record_consumed(self, lag: int) -> None:
        with self._lock:
            self.events_received += 1
            self.events_valid += 1
            self.consumer_status = "RUNNING"
            now_iso = datetime.now(timezone.utc).isoformat()
            self.last_consumed_at = now_iso
            self.consumer_lag_samples.append(lag)
            self.lag_history.append({"timestamp": now_iso, "consumer_lag": lag})
            if len(self.lag_history) > 300:
                self.lag_history = self.lag_history[-300:]

    def record_consumer_error(self) -> None:
        with self._lock:
            self.consumer_errors += 1
            self.events_invalid += 1

    def set_producer_done(self) -> None:
        with self._lock:
            self.producer_status = "COMPLETED"

    def set_consumer_done(self) -> None:
        with self._lock:
            self.consumer_status = "COMPLETED"

    def update_agents_status(self, agents: List[Dict]) -> None:
        with self._lock:
            self.agents_status = agents

    def add_ai_finding(self, finding: Dict) -> None:
        with self._lock:
            self.ai_findings.append(finding)

    def update_window_status(self, ws: Dict) -> None:
        with self._lock:
            self.window_status = ws

    def snapshot(self) -> Dict:
        """Return a thread-safe copy of the state for API serialisation."""
        with self._lock:
            elapsed = time.time() - self.started_at
            lag_samples = list(self.consumer_lag_samples)
            lag_avg = round(sum(lag_samples) / len(lag_samples), 2) if lag_samples else 0.0
            producer_rate = round(self.events_published / max(1.0, elapsed), 2)
            consumer_rate = round(self.events_received / max(1.0, elapsed), 2)
            return {
                "run_id": self.run_id,
                "uptime_seconds": round(elapsed, 1),
                "events_published": self.events_published,
                "events_received": self.events_received,
                "events_valid": self.events_valid,
                "events_invalid": self.events_invalid,
                "consumer_lag_avg": lag_avg,
                "consumer_lag_max": max(lag_samples, default=0),
                "producer_status": self.producer_status,
                "producer_errors": self.producer_errors,
                "last_published_at": self.last_published_at,
                "consumer_status": self.consumer_status,
                "consumer_errors": self.consumer_errors,
                "last_consumed_at": self.last_consumed_at,
                "producer_rate": producer_rate,
                "consumer_rate": consumer_rate,
                "lag_history": list(self.lag_history),
                "throughput_history": list(self.throughput_history),
                "recent_events": list(self.recent_events),
                "ai_findings": list(self.ai_findings),
                "agents_status": list(self.agents_status),
                "window_status": dict(self.window_status),
                "target_events": self.target_events,
            }


# ─── Module-level registry ───────────────────────────────────────────────────

_stream_states: Dict[str, StreamingState] = {}
_registry_lock = Lock()


def create_state(run_id: str, target_events: int = 500) -> StreamingState:
    with _registry_lock:
        state = StreamingState(run_id=run_id, target_events=target_events)
        _stream_states[run_id] = state
        return state


def get_state(run_id: str) -> Optional[StreamingState]:
    return _stream_states.get(run_id)


def get_or_create(run_id: str, target_events: int = 500) -> StreamingState:
    existing = get_state(run_id)
    if existing:
        return existing
    return create_state(run_id, target_events)
