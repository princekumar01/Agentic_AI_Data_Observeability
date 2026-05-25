"""
backend/services/dashboard_service.py
─────────────────────────────────────────────────────
Reads run artefacts from output/runs/ and aggregates
dashboard metrics. Returns 403 if run not approved.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


RUNS_DIR = os.path.join("output", "runs")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _list_run_dirs() -> List[str]:
    if not os.path.isdir(RUNS_DIR):
        return []
    return [
        d for d in os.listdir(RUNS_DIR)
        if os.path.isdir(os.path.join(RUNS_DIR, d))
    ]


def _load_json(path: str) -> Optional[Dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _run_status(run_id: str) -> str:
    audit = _load_json(os.path.join(RUNS_DIR, run_id, "audit_trail.json"))
    if not audit:
        return "unknown"
    return audit.get("pipeline_status", "unknown")


def _run_review_status(run_id: str) -> Optional[str]:
    audit = _load_json(os.path.join(RUNS_DIR, run_id, "audit_trail.json"))
    if not audit:
        return None
    return audit.get("hitl_decision", {}).get("decision")


def _is_approved(run_id: str) -> bool:
    status = _run_status(run_id)
    decision = _run_review_status(run_id)
    return status == "approved" or decision == "approved"


def _load_metrics(run_id: str) -> Optional[Dict]:
    for fname in ("sanitized_metrics.json", "rolling_metrics.json"):
        m = _load_json(os.path.join(RUNS_DIR, run_id, fname))
        if m:
            return m
    return None


def _load_token_usage(run_id: str) -> List[Dict]:
    path = os.path.join(RUNS_DIR, run_id, "token_usage.json")
    data = _load_json(path)
    if isinstance(data, list):
        return data
    return []


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_audit(run_id: str) -> Optional[Dict]:
    return _load_json(os.path.join(RUNS_DIR, run_id, "audit_trail.json"))


def _audit_time_bounds(run_id: str) -> tuple[Optional[datetime], Optional[datetime]]:
    audit = _load_audit(run_id) or {}
    entries = audit.get("entries", [])
    timestamps = [
        parsed for parsed in (_parse_dt(e.get("timestamp")) for e in entries)
        if parsed is not None
    ]
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


# ─── Public API ──────────────────────────────────────────────────────────────

def get_summary(period: str = "24h") -> Dict[str, Any]:
    runs = _list_run_dirs()
    total = len(runs)
    completed = sum(1 for r in runs if _run_status(r) in ("completed", "approved", "pending_review"))
    failed = sum(1 for r in runs if _run_status(r) == "failed")
    in_progress = total - completed - failed

    anomalies = 0
    critical = 0
    confidence_scores: List[float] = []

    for run_id in runs:
        m = _load_metrics(run_id)
        if m:
            anomalies += m.get("anomaly_count", 0)
            dist = m.get("distribution", {}).get("severity_distribution", {})
            critical += dist.get("Critical", 0)
        conf_path = os.path.join(RUNS_DIR, run_id, "agent_confidence.json")
        conf = _load_json(conf_path)
        if conf and isinstance(conf, dict):
            scores = [v for v in conf.values() if isinstance(v, (int, float))]
            confidence_scores.extend(scores)

    avg_conf = round(sum(confidence_scores) / len(confidence_scores), 1) if confidence_scores else 0.0

    return {
        "period": period,
        "total_runs": total,
        "total_runs_change_pct": 0.0,
        "completed_runs": completed,
        "completed_runs_change_pct": 0.0,
        "anomalies_detected": anomalies,
        "anomalies_change_pct": 0.0,
        "critical_issues": critical,
        "critical_issues_change_pct": 0.0,
        "avg_confidence_score": avg_conf,
        "avg_confidence_change_pct": 0.0,
    }


def get_pipeline_runs_over_time(period: str = "24h", granularity: str = "hourly") -> Dict[str, Any]:
    runs = _list_run_dirs()
    now = datetime.now(timezone.utc)
    bucket_count = 24 if granularity == "hourly" else 7
    delta = timedelta(hours=1) if granularity == "hourly" else timedelta(days=1)
    fmt = "%H:00" if granularity == "hourly" else "%Y-%m-%d"

    buckets: Dict[str, Dict[str, Any]] = {}
    for i in range(bucket_count - 1, -1, -1):
        bucket_time = now - (delta * i)
        label = bucket_time.strftime(fmt)
        buckets[label] = {"time": label, "completed": 0, "failed": 0, "in_progress": 0}

    for run_id in runs:
        start, end = _audit_time_bounds(run_id)
        event_time = end or start
        if not event_time:
            continue
        label = event_time.strftime(fmt)
        if label not in buckets:
            continue
        status = _run_status(run_id)
        if status in ("completed", "approved", "pending_review"):
            buckets[label]["completed"] += 1
        elif status == "failed":
            buckets[label]["failed"] += 1
        else:
            buckets[label]["in_progress"] += 1

    data = list(buckets.values())
    return {"granularity": granularity, "data": data}


def get_anomalies_by_severity(period: str = "24h") -> Dict[str, Any]:
    runs = _list_run_dirs()
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for run_id in runs:
        m = _load_metrics(run_id)
        if m:
            dist = m.get("distribution", {}).get("severity_distribution", {})
            for k in counts:
                counts[k] += dist.get(k, 0)
    total = sum(counts.values()) or 1
    colors = {"Critical": "#EF4444", "High": "#F59E0B", "Medium": "#3B82F6", "Low": "#10B981"}
    breakdown = [
        {"severity": k, "count": v, "pct": round(v / total * 100, 1), "color": colors[k]}
        for k, v in counts.items()
    ]
    return {"total": sum(counts.values()), "breakdown": breakdown, "change_pct": 0.0}


def get_agents_performance(period: str = "24h") -> Dict[str, Any]:
    agent_names = [
        "data_quality_agent",
        "log_analysis_agent",
        "rca_agent",
        "recommendation_agent",
        "compliance_agent",
    ]
    runs = _list_run_dirs()
    agent_stats: Dict[str, Dict] = {
        a: {"runs": 0, "confidence_sum": 0.0, "issues": 0} for a in agent_names
    }
    for run_id in runs:
        conf = _load_json(os.path.join(RUNS_DIR, run_id, "agent_confidence.json"))
        if conf and isinstance(conf, dict):
            for a in agent_names:
                if a in conf:
                    agent_stats[a]["runs"] += 1
                    agent_stats[a]["confidence_sum"] += conf[a]
                    if conf[a] < 75:
                        agent_stats[a]["issues"] += 1
    agents = []
    for a in agent_names:
        s = agent_stats[a]
        avg = round(s["confidence_sum"] / s["runs"], 1) if s["runs"] > 0 else 0.0
        agents.append({
            "name": a.replace("_", " ").title(),
            "status": "Active" if s["runs"] > 0 else "No Data",
            "runs": s["runs"],
            "avg_confidence": avg,
            "issues": s["issues"],
        })
    return {"agents": agents}


def get_token_usage_summary(period: str = "24h") -> Dict[str, Any]:
    runs = _list_run_dirs()
    total_tokens = 0
    total_cost = 0.0
    agent_totals: Dict[str, int] = {}
    by_run: List[Dict[str, Any]] = []

    for run_id in runs:
        records = _load_token_usage(run_id)
        run_tokens = 0
        run_cost = 0.0
        for rec in records:
            t = rec.get("total_tokens", 0)
            total_tokens += t
            run_tokens += t
            c = rec.get("estimated_cost_usd", 0.0)
            total_cost += c
            run_cost += c
            name = rec.get("agent_name", "unknown")
            agent_totals[name] = agent_totals.get(name, 0) + t
        if records:
            by_run.append({
                "run_id": run_id,
                "total_tokens": run_tokens,
                "total_cost_usd": round(run_cost, 6),
            })

    total_runs = len(runs) or 1
    cost_per_run = round(total_cost / total_runs, 6)
    grand_total = total_tokens or 1
    by_agent = [
        {"name": k, "tokens": v, "pct": round(v / grand_total * 100, 1)}
        for k, v in agent_totals.items()
    ]
    return {
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "runs": len(runs),
        "cost_per_run": cost_per_run,
        "by_agent": by_agent,
        "by_run": by_run,
    }


def get_pipeline_health() -> Dict[str, Any]:
    runs = _list_run_dirs()
    completed = sum(1 for r in runs if _run_status(r) in ("completed", "approved"))
    total = len(runs) or 1
    success_rate = round(completed / total * 100, 1)
    scores = [
        m.get("health_score")
        for r in runs
        for m in [_load_metrics(r)]
        if m and isinstance(m.get("health_score"), (int, float))
    ]
    health_score = round(sum(scores) / len(scores), 1) if scores else success_rate
    health_label = (
        "Excellent" if health_score >= 90 else
        "Good" if health_score >= 75 else
        "Fair" if health_score >= 60 else "Poor"
    )
    durations: List[float] = []
    for run_id in runs:
        start, end = _audit_time_bounds(run_id)
        if start and end and end >= start:
            durations.append((end - start).total_seconds())
    return {
        "health_score": health_score,
        "health_label": health_label,
        "availability_pct": success_rate,
        "success_rate_pct": success_rate,
        "avg_processing_time_seconds": round(sum(durations) / len(durations), 1) if durations else 0.0,
        "events_processed": sum(
            (_load_metrics(r) or {}).get("total_rows", 0) for r in runs
        ),
    }


def get_anomalies_trend(period: str = "7d", granularity: str = "daily") -> Dict[str, Any]:
    runs = _list_run_dirs()
    buckets: Dict[str, Dict[str, int | str]] = {}
    for i in range(6, -1, -1):
        date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[date] = {"date": date, "critical": 0, "high": 0, "medium": 0, "low": 0}

    for run_id in runs:
        metrics = _load_metrics(run_id)
        if not metrics:
            continue
        _, end = _audit_time_bounds(run_id)
        label = (end or _parse_dt(metrics.get("computed_at")) or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        if label not in buckets:
            continue
        dist = metrics.get("distribution", {}).get("severity_distribution", {})
        buckets[label]["critical"] = int(buckets[label]["critical"]) + dist.get("Critical", 0)
        buckets[label]["high"] = int(buckets[label]["high"]) + dist.get("High", 0)
        buckets[label]["medium"] = int(buckets[label]["medium"]) + dist.get("Medium", 0)
        buckets[label]["low"] = int(buckets[label]["low"]) + dist.get("Low", 0)

    return {"data": list(buckets.values())}


def get_top_anomaly_types(period: str = "24h", limit: int = 5) -> Dict[str, Any]:
    type_counts: Dict[str, int] = {}
    runs = _list_run_dirs()
    for run_id in runs:
        m = _load_metrics(run_id)
        if m:
            for anomaly in m.get("anomalies", []):
                key = anomaly.split(":")[0].strip()[:50]
                type_counts[key] = type_counts.get(key, 0) + 1
    total = sum(type_counts.values()) or 1
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {
        "anomaly_types": [
            {"type": k, "count": v, "pct": round(v / total * 100, 1)}
            for k, v in sorted_types
        ]
    }


def get_run_status_distribution(period: str = "24h") -> Dict[str, Any]:
    runs = _list_run_dirs()
    total = len(runs) or 1
    completed = sum(1 for r in runs if _run_status(r) in ("completed", "approved", "pending_review"))
    failed = sum(1 for r in runs if _run_status(r) == "failed")
    in_progress = total - completed - failed
    return {
        "total": len(runs),
        "completed": {"count": completed, "pct": round(completed / total * 100, 1)},
        "failed": {"count": failed, "pct": round(failed / total * 100, 1)},
        "in_progress": {"count": in_progress, "pct": round(in_progress / total * 100, 1)},
        "change_pct": 0.0,
    }


def get_run_tokens(run_id: str) -> Dict[str, Any]:
    """Returns 403-signal (raises) if run not approved."""
    if not _is_approved(run_id):
        raise PermissionError(f"Run {run_id} is not yet approved.")
    records = _load_token_usage(run_id)
    per_agent = []
    run_total_tokens = 0
    run_total_cost = 0.0
    for rec in records:
        t = rec.get("total_tokens", 0)
        c = rec.get("estimated_cost_usd", 0.0)
        run_total_tokens += t
        run_total_cost += c
        per_agent.append({
            "agent": rec.get("agent_name"),
            "total_tokens": t,
            "estimated_cost_usd": c,
        })
    return {
        "per_agent": per_agent,
        "run_total_tokens": run_total_tokens,
        "run_total_cost_usd": round(run_total_cost, 6),
    }
