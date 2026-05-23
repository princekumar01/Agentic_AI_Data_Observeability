"""
backend/services/alert_service.py
─────────────────────────────────────────────────────
Writes alerts to output/alerts/alerts.json and alerts.log.
All alerts are local files only — no external webhooks.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

_ALERTS_DIR = os.path.join("output", "alerts")
_ALERTS_JSON = os.path.join(_ALERTS_DIR, "alerts.json")
_ALERTS_LOG = os.path.join(_ALERTS_DIR, "alerts.log")

_lock = Lock()


def _ensure_dirs() -> None:
    os.makedirs(_ALERTS_DIR, exist_ok=True)


def _load_alerts() -> List[Dict]:
    if not os.path.exists(_ALERTS_JSON):
        return []
    try:
        with open(_ALERTS_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_alerts(alerts: List[Dict]) -> None:
    tmp = _ALERTS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(alerts, fh, indent=2)
    os.replace(tmp, _ALERTS_JSON)


# ─── Public API ──────────────────────────────────────────────────────────────

def write_alert(
    severity: str,
    message: str,
    run_id: Optional[str] = None,
    source: str = "pipeline",
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an alert, persist it, and return the alert dict."""
    _ensure_dirs()

    alert_id = f"ALT_{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    alert: Dict[str, Any] = {
        "id": alert_id,
        "severity": severity.upper(),
        "title": title or message[:80],
        "description": message,
        "source": source,
        "run_id": run_id,
        "timestamp": now,
        "time": now,
        "status": "New",
        "read": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "escalated_by": None,
        "escalated_at": None,
        "history": [],
    }

    with _lock:
        alerts = _load_alerts()
        alerts.append(alert)
        _save_alerts(alerts)

        # Human-readable log line
        with open(_ALERTS_LOG, "a", encoding="utf-8") as log_fh:
            log_fh.write(
                f"[{now}] [{severity.upper():8s}] {source} | run={run_id} | {message}\n"
            )

    return alert


def get_all_alerts(
    severity_filter: str = "all",
    source_filter: str = "all",
    status_filter: str = "all",
    from_dt: Optional[str] = None,
    to_dt: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
) -> Dict[str, Any]:
    """Return paginated, filtered alerts list with summary counts."""
    _ensure_dirs()
    all_alerts = _load_alerts()

    # Filter
    filtered = []
    for a in all_alerts:
        if severity_filter != "all" and a.get("severity", "").upper() != severity_filter.upper():
            continue
        if source_filter != "all" and a.get("source", "") != source_filter:
            continue
        if status_filter != "all" and a.get("status", "") != status_filter:
            continue
        if from_dt and a.get("timestamp", "") < from_dt:
            continue
        if to_dt and a.get("timestamp", "") > to_dt:
            continue
        filtered.append(a)

    # Sort newest first
    filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Summary counts
    severity_counts: Dict[str, int] = {"CRITICAL": 0, "WARNING": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for a in all_alerts:
        s = a.get("severity", "INFO").upper()
        severity_counts[s] = severity_counts.get(s, 0) + 1

    total = len(filtered)
    start = (page - 1) * limit
    page_alerts = filtered[start : start + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "summary": {
            "critical": severity_counts.get("CRITICAL", 0),
            "high": severity_counts.get("HIGH", 0) + severity_counts.get("WARNING", 0),
            "medium": severity_counts.get("MEDIUM", 0),
            "low": severity_counts.get("LOW", 0) + severity_counts.get("INFO", 0),
            "total_24h": len(all_alerts),
            "change_pct": 0.0,
        },
        "alerts": page_alerts,
    }


def get_alert_by_id(alert_id: str) -> Optional[Dict]:
    alerts = _load_alerts()
    for a in alerts:
        if a.get("id") == alert_id:
            return a
    return None


def acknowledge_alert(alert_id: str, acknowledged_by: str, note: Optional[str] = None) -> bool:
    with _lock:
        alerts = _load_alerts()
        for a in alerts:
            if a.get("id") == alert_id:
                now = datetime.now(timezone.utc).isoformat()
                a["status"] = "Acknowledged"
                a["acknowledged_by"] = acknowledged_by
                a["acknowledged_at"] = now
                a.setdefault("history", []).append({
                    "action": f"Acknowledged{(': ' + note) if note else ''}",
                    "by": acknowledged_by,
                    "at": now,
                })
                _save_alerts(alerts)
                return True
    return False


def escalate_alert(alert_id: str, escalated_by: str, reason: Optional[str] = None) -> bool:
    with _lock:
        alerts = _load_alerts()
        for a in alerts:
            if a.get("id") == alert_id:
                now = datetime.now(timezone.utc).isoformat()
                a["status"] = "Escalated"
                a["escalated_by"] = escalated_by
                a["escalated_at"] = now
                a.setdefault("history", []).append({
                    "action": f"Escalated{(': ' + reason) if reason else ''}",
                    "by": escalated_by,
                    "at": now,
                })
                _save_alerts(alerts)
                return True
    return False


def mark_alert_read(alert_id: str) -> bool:
    with _lock:
        alerts = _load_alerts()
        for a in alerts:
            if a.get("id") == alert_id:
                a["read"] = True
                if a.get("status") == "New":
                    a["status"] = "In Progress"
                _save_alerts(alerts)
                return True
    return False


def get_unread_count() -> int:
    alerts = _load_alerts()
    return sum(1 for a in alerts if not a.get("read", False))
