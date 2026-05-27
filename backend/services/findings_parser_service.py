"""
backend/services/findings_parser_service.py
─────────────────────────────────────────────────────
Per-agent specialized parsers that convert raw LLM responses
into the AgentFindings schema consumed by the frontend.

Each of the 5 agents emits a distinct, well-known text format
(documented in `backend/agents/*.py`).  We parse each one with
a dedicated function and enrich the KeyFindings with real numeric
context pulled from sanitized_metrics.json.

Public API:
    parse_agent_findings(agent_name, response_text, confidence, metrics) -> AgentFindings

The output schema (`AgentFindings` from backend/models/schemas.py) is
locked — the frontend depends on those exact field names.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from backend.models.schemas import AgentFindings, KeyFinding


# ─── Public entry point ──────────────────────────────────────────────────────

def parse_agent_findings(
    agent_name: str,
    response_text: str,
    confidence: int,
    metrics: Dict[str, Any],
) -> AgentFindings:
    """Dispatch to the agent-specific parser; falls back to a generic parser."""
    parser = _PARSERS.get(agent_name, _parse_generic)
    return parser(agent_name, response_text, confidence, metrics)


# ─── Shared utilities ────────────────────────────────────────────────────────

def _confidence_label(c: int) -> str:
    if c >= 90:
        return "Very High"
    if c >= 75:
        return "High"
    if c >= 60:
        return "Medium"
    return "Low"


def _severity_from_status(status: str) -> str:
    """data_quality_agent: PASS / WARN / FAIL → Low / Medium / High."""
    s = status.upper().strip()
    if s == "PASS":
        return "Low"
    if s == "WARN":
        return "Medium"
    if s == "FAIL":
        return "High"
    return "Medium"


def _severity_from_priority(priority: str) -> str:
    """RCA / Recommendation priorities → severity."""
    p = priority.lower().strip()
    if "critical" in p:
        return "Critical"
    if "immediate" in p or "high" in p:
        return "High"
    if "medium" in p or "short" in p:
        return "Medium"
    if "low" in p or "long" in p:
        return "Low"
    return "Medium"


def _trend_from_severity(severity: str) -> str:
    """User-selected mapping: severity drives trend (no historical data yet)."""
    s = severity.lower()
    if s in ("critical", "high"):
        return "worsening"
    if s == "low":
        return "improving"
    return "stable"


# Matches lines that look like an ALL-CAPS header followed by ':'
_HEADER_RE = re.compile(r"^[A-Z][A-Z0-9 /\-]*:")


def _section(text: str, header: str) -> str:
    """
    Return the value following `HEADER:`.  Continuation lines (not starting
    with another ALL-CAPS header) are appended.  Returns "" if not found.
    """
    target = header.upper().rstrip(":") + ":"
    capturing = False
    captured: List[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not capturing:
            if line.upper().startswith(target):
                rest = line.split(":", 1)[1].strip() if ":" in line else ""
                if rest:
                    captured.append(rest)
                capturing = True
        else:
            if _HEADER_RE.match(line):
                break
            if line:
                captured.append(line)
    return " ".join(captured).strip()


def _truncate(s: str, n: int) -> str:
    """Truncate at the last whitespace before `n` chars and append an ellipsis."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _pct(num: float, den: float) -> float:
    if not den:
        return 0.0
    return round(num / den * 100, 2)


# ─── Specialized parser: data_quality_agent ──────────────────────────────────

def _parse_data_quality(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    """Format: 5 × (PILLAR: / STATUS: / FINDING:) + OVERALL SEVERITY: + SUMMARY:"""
    pillar_blocks = re.split(r"(?=^PILLAR:)", response, flags=re.MULTILINE)
    pillar_blocks = [b.strip() for b in pillar_blocks if b.strip().startswith("PILLAR:")]

    key_findings: List[KeyFinding] = []

    for block in pillar_blocks:
        pillar_name = ""
        status = ""
        finding = ""
        for raw_line in block.split("\n"):
            line = raw_line.strip()
            if line.startswith("PILLAR:"):
                pillar_name = line.split(":", 1)[1].strip()
            elif line.startswith("STATUS:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("FINDING:"):
                finding = line.split(":", 1)[1].strip()
            elif finding and not _HEADER_RE.match(line) and line:
                finding += " " + line

        if not pillar_name or not finding:
            continue

        severity = _severity_from_status(status)
        affected, total, percentage = _metrics_for_pillar(pillar_name, metrics)

        key_findings.append(KeyFinding(
            issue=_truncate(finding, 200),
            severity=severity,
            affected=affected,
            total=total,
            percentage=percentage,
            trend=_trend_from_severity(severity),
        ))

    summary = _section(response, "SUMMARY") or _truncate(response, 300)
    overall_severity = _section(response, "OVERALL SEVERITY")
    insight = f"Overall Severity: {overall_severity}" if overall_severity else ""
    evidence = _evidence_from_metrics(metrics)

    overall_bad = overall_severity.lower() in ("critical", "high")
    flag = (
        confidence < 75
        or any(kf.severity in ("Critical", "High") for kf in key_findings)
        or overall_bad
    )

    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=flag,
        summary=summary,
        key_findings=key_findings,
        evidence=evidence,
        recommendations="",
        insight=insight,
    )


# ─── Specialized parser: log_analysis_agent ──────────────────────────────────

def _parse_log_analysis(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    """Format: ERROR COUNT / WARNING COUNT / KAFKA ISSUES / API ISSUES /
    DATA QUALITY WARNINGS / OPERATIONAL STATUS / SUMMARY."""
    log_summary = metrics.get("log_summary", {})
    streaming = metrics.get("streaming", {})

    # Use metric values as the source of truth; fall back to parsed counts.
    err_in_text = _first_int(_section(response, "ERROR COUNT"))
    warn_in_text = _first_int(_section(response, "WARNING COUNT"))
    errors = int(log_summary.get("total_errors", err_in_text))
    warnings = int(log_summary.get("total_warnings", warn_in_text))
    info_lines = int(log_summary.get("total_info", 0))
    total_log_lines = errors + warnings + info_lines

    kafka_status = _section(response, "KAFKA ISSUES") or "None detected"
    api_status = _section(response, "API ISSUES") or "None detected"
    dq_warnings = _section(response, "DATA QUALITY WARNINGS") or "None detected"
    operational = _section(response, "OPERATIONAL STATUS") or "UNKNOWN"
    summary = _section(response, "SUMMARY") or _truncate(response, 300)

    consumer_lag = float(streaming.get("consumer_lag_avg", 0))
    schema_errors_stream = int(streaming.get("schema_errors_in_stream", 0))
    events_in_window = int(streaming.get("events_in_window", 0))

    key_findings: List[KeyFinding] = []

    if errors > 0:
        sev = "Critical"
        key_findings.append(KeyFinding(
            issue=f"Errors in ETL log ({errors} occurrence{'s' if errors != 1 else ''})",
            severity=sev,
            affected=errors,
            total=total_log_lines,
            percentage=_pct(errors, total_log_lines),
            trend=_trend_from_severity(sev),
        ))

    if warnings > 0:
        sev = "Medium"
        key_findings.append(KeyFinding(
            issue=f"Warnings in ETL log ({warnings} occurrence{'s' if warnings != 1 else ''}) — review for impact",
            severity=sev,
            affected=warnings,
            total=total_log_lines,
            percentage=_pct(warnings, total_log_lines),
            trend=_trend_from_severity(sev),
        ))

    if consumer_lag > 0:
        sev = "Medium" if consumer_lag > 1000 else "Low"
        key_findings.append(KeyFinding(
            issue=f"Average Kafka consumer lag: {consumer_lag:.0f} ms",
            severity=sev,
            affected=int(consumer_lag),
            total=0,
            percentage=0.0,
            trend=_trend_from_severity(sev),
        ))

    if schema_errors_stream > 0:
        sev = "High"
        key_findings.append(KeyFinding(
            issue=f"Schema errors during streaming ({schema_errors_stream} of {events_in_window} events)",
            severity=sev,
            affected=schema_errors_stream,
            total=events_in_window,
            percentage=_pct(schema_errors_stream, events_in_window),
            trend=_trend_from_severity(sev),
        ))

    if "none" not in kafka_status.lower():
        key_findings.append(KeyFinding(
            issue=f"Kafka issue: {_truncate(kafka_status, 150)}",
            severity="High",
            affected=0,
            total=0,
            percentage=0.0,
            trend="worsening",
        ))

    if "none" not in api_status.lower():
        key_findings.append(KeyFinding(
            issue=f"API issue: {_truncate(api_status, 150)}",
            severity="High",
            affected=0,
            total=0,
            percentage=0.0,
            trend="worsening",
        ))

    evidence = (
        f"Errors: {errors} | Warnings: {warnings} | "
        f"Kafka: {kafka_status} | API: {api_status} | "
        f"Data Quality Warnings: {dq_warnings} | "
        f"Consumer lag avg: {consumer_lag:.0f} ms"
    )
    insight = f"Operational Status: {operational}"

    healthy = operational.upper() in ("HEALTHY", "OK", "GREEN", "GOOD", "NOMINAL")
    flag = (
        confidence < 75
        or any(kf.severity in ("Critical", "High") for kf in key_findings)
        or not healthy
    )

    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=flag,
        summary=summary,
        key_findings=key_findings,
        evidence=evidence,
        recommendations="",
        insight=insight,
    )


# ─── Specialized parser: rca_agent ───────────────────────────────────────────

def _parse_rca(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    """Format: TOTAL INCIDENTS DETECTED: N + N × (INCIDENT: title | PRIORITY: lvl
    + ROOT CAUSE / EVIDENCE / IMPACT) + OVERALL PIPELINE HEALTH + ROOT CAUSE SUMMARY."""
    incident_blocks = re.split(r"(?=^INCIDENT:)", response, flags=re.MULTILINE)
    incident_blocks = [b.strip() for b in incident_blocks if b.strip().startswith("INCIDENT:")]

    key_findings: List[KeyFinding] = []
    evidence_parts: List[str] = []

    for block in incident_blocks:
        first_line = block.split("\n", 1)[0]
        m = re.match(
            r"INCIDENT:\s*(.*?)\s*\|\s*PRIORITY:\s*(.*)",
            first_line,
            flags=re.IGNORECASE,
        )
        if not m:
            continue
        title = m.group(1).strip()
        priority = m.group(2).strip()

        root_cause = ""
        evidence_line = ""
        impact = ""
        current_field: str = ""
        for raw_line in block.split("\n")[1:]:
            line = raw_line.strip()
            if line.upper().startswith("ROOT CAUSE:"):
                root_cause = line.split(":", 1)[1].strip()
                current_field = "root_cause"
            elif line.upper().startswith("EVIDENCE:"):
                evidence_line = line.split(":", 1)[1].strip()
                current_field = "evidence"
            elif line.upper().startswith("IMPACT:"):
                impact = line.split(":", 1)[1].strip()
                current_field = "impact"
            elif _HEADER_RE.match(line):
                current_field = ""
            elif line and current_field:
                if current_field == "root_cause":
                    root_cause += " " + line
                elif current_field == "evidence":
                    evidence_line += " " + line
                elif current_field == "impact":
                    impact += " " + line

        severity = _severity_from_priority(priority)
        affected, total, percentage = _metrics_for_incident(title, root_cause, metrics)

        issue = f"{title} — {root_cause}" if root_cause else title
        key_findings.append(KeyFinding(
            issue=_truncate(issue, 200),
            severity=severity,
            affected=affected,
            total=total,
            percentage=percentage,
            trend=_trend_from_severity(severity),
        ))

        if evidence_line:
            evidence_parts.append(evidence_line.strip(' "'))

    summary = (
        _section(response, "ROOT CAUSE SUMMARY")
        or _section(response, "SUMMARY")
        or _truncate(response, 300)
    )
    pipeline_health = _section(response, "OVERALL PIPELINE HEALTH")
    insight = f"Pipeline Health: {pipeline_health}" if pipeline_health else ""
    evidence = " | ".join(evidence_parts)

    bad_health = pipeline_health.upper() in ("DEGRADED", "CRITICAL", "FAILED", "DOWN", "RED")
    flag = (
        confidence < 75
        or any(kf.severity in ("Critical", "High") for kf in key_findings)
        or bad_health
    )

    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=flag,
        summary=summary,
        key_findings=key_findings,
        evidence=evidence,
        recommendations="",
        insight=insight,
    )


# ─── Specialized parser: recommendation_agent ────────────────────────────────

def _parse_recommendation(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    """Format: N × (PRIORITY / RESPONSIBLE TEAM / ACTION / RATIONALE)
    + PREVENTIVE MEASURES (bulleted)."""
    rec_blocks = re.split(r"(?=^PRIORITY:)", response, flags=re.MULTILINE)
    rec_blocks = [b.strip() for b in rec_blocks if b.strip().startswith("PRIORITY:")]

    key_findings: List[KeyFinding] = []
    actions_list: List[str] = []
    rationale_list: List[str] = []
    priority_counts: Dict[str, int] = {}
    teams: List[str] = []
    has_immediate = False

    for block in rec_blocks:
        priority = ""
        team = ""
        action = ""
        rationale = ""
        for raw_line in block.split("\n"):
            line = raw_line.strip()
            if line.upper().startswith("PRIORITY:"):
                priority = line.split(":", 1)[1].strip()
            elif line.upper().startswith("RESPONSIBLE TEAM:"):
                team = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ACTION:"):
                action = line.split(":", 1)[1].strip()
            elif line.upper().startswith("RATIONALE:"):
                rationale = line.split(":", 1)[1].strip()

        if not action:
            continue

        # Stop the PREVENTIVE MEASURES section bleeding into the last RATIONALE
        if "PREVENTIVE MEASURES" in rationale.upper():
            rationale = rationale.split("PREVENTIVE MEASURES")[0].strip()

        if priority:
            key = priority.title()
            priority_counts[key] = priority_counts.get(key, 0) + 1
            if "immediate" in priority.lower():
                has_immediate = True
        if team and team not in teams:
            teams.append(team)

        actions_list.append(action)
        if rationale:
            rationale_list.append(rationale)

        severity = _severity_from_priority(priority)
        key_findings.append(KeyFinding(
            issue=_truncate(action, 200),
            severity=severity,
            affected=0,
            total=0,
            percentage=0.0,
            trend=_trend_from_severity(severity),
        ))

    preventive = _section(response, "PREVENTIVE MEASURES")

    n_total = len(actions_list)
    if n_total > 0:
        priority_breakdown = ", ".join(
            f"{cnt} {prio.lower()}" for prio, cnt in priority_counts.items()
        )
        team_summary = ", ".join(teams) if teams else "various"
        summary = (
            f"{n_total} action{'s' if n_total != 1 else ''} recommended "
            f"({priority_breakdown}). Responsible teams: {team_summary}."
        )
    else:
        summary = _truncate(response, 300)

    recommendations = "; ".join(actions_list)
    evidence = " | ".join(rationale_list)
    insight = _truncate(preventive, 300) if preventive else ""

    flag = (
        confidence < 75
        or any(kf.severity in ("Critical", "High") for kf in key_findings)
        or has_immediate
    )

    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=flag,
        summary=summary,
        key_findings=key_findings,
        evidence=evidence,
        recommendations=recommendations,
        insight=insight,
    )


# ─── Specialized parser: compliance_agent ────────────────────────────────────

def _parse_compliance(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    """Format: COMPLIANCE STATUS / PHI-PII CHECK / COMPLETENESS CHECK /
    GCP ALIGNMENT / REGULATORY NOTES / FINAL RECOMMENDATION."""
    compliance_status = _section(response, "COMPLIANCE STATUS") or "UNKNOWN"
    phi_pii = _section(response, "PHI/PII CHECK")
    completeness = _section(response, "COMPLETENESS CHECK")
    gcp = _section(response, "GCP ALIGNMENT")
    regulatory = _section(response, "REGULATORY NOTES")
    final_rec = _section(response, "FINAL RECOMMENDATION")

    is_non_compliant = "non-compliant" in compliance_status.lower()

    key_findings: List[KeyFinding] = []
    for label, text in (
        ("PHI/PII Masking", phi_pii),
        ("Data Completeness", completeness),
        ("ICH E6 GCP Alignment", gcp),
        ("FDA 21 CFR Part 11", regulatory),
    ):
        if not text:
            continue
        sev = _severity_from_compliance_text(text)
        key_findings.append(KeyFinding(
            issue=f"{label}: {_truncate(text, 180)}",
            severity=sev,
            affected=0,
            total=0,
            percentage=0.0,
            trend=_trend_from_severity(sev),
        ))

    summary_parts = [f"Compliance Status: {compliance_status}."]
    if completeness:
        summary_parts.append(_truncate(completeness, 200))
    if gcp:
        summary_parts.append(_truncate(gcp, 200))
    summary = " ".join(summary_parts) if compliance_status != "UNKNOWN" else _truncate(response, 300)

    evidence = _truncate(phi_pii, 300) if phi_pii else ""
    insight = final_rec

    flag = (
        confidence < 75
        or any(kf.severity in ("Critical", "High") for kf in key_findings)
        or is_non_compliant
    )

    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=flag,
        summary=summary,
        key_findings=key_findings,
        evidence=evidence,
        recommendations="",
        insight=insight,
    )


def _severity_from_compliance_text(text: str) -> str:
    t = text.lower()
    if "non-compliant" in t or "violation" in t or "fails" in t or "breach" in t:
        return "High"
    if (
        "issue" in t
        or "deficien" in t
        or "may impact" in t
        or "warning" in t
        or "concern" in t
    ):
        return "Medium"
    return "Low"


# ─── Generic fallback (unknown agent or malformed response) ──────────────────

def _parse_generic(
    agent_name: str, response: str, confidence: int, metrics: Dict[str, Any]
) -> AgentFindings:
    return AgentFindings(
        name=agent_name,
        status="COMPLETED" if response else "MISSING",
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        flag_for_review=confidence < 75,
        summary=_truncate(response, 300),
        key_findings=[],
        evidence="",
        recommendations="",
        insight="",
    )


_PARSERS = {
    "data_quality_agent": _parse_data_quality,
    "log_analysis_agent": _parse_log_analysis,
    "rca_agent": _parse_rca,
    "recommendation_agent": _parse_recommendation,
    "compliance_agent": _parse_compliance,
}


# ─── Metrics joiners ─────────────────────────────────────────────────────────

def _first_int(s: str, default: int = 0) -> int:
    m = re.search(r"-?\d+", s or "")
    return int(m.group(0)) if m else default


def _metrics_for_pillar(
    pillar_name: str, metrics: Dict[str, Any]
) -> Tuple[int, int, float]:
    """Pick the right authoritative numbers from sanitized_metrics.json
    for a given Data Quality pillar."""
    p = pillar_name.lower()
    total_rows = int(metrics.get("total_rows", 0))

    if "volume" in p:
        vol = metrics.get("volume", {})
        return (
            int(vol.get("total_rows", 0)),
            int(vol.get("expected_rows", 0)),
            float(vol.get("volume_pct", 0.0)),
        )
    if "fresh" in p:
        fresh = metrics.get("freshness", {})
        days = int(fresh.get("days_since_last_visit", 0))
        max_days = int(fresh.get("freshness_max_days", 1)) or 1
        return (days, max_days, _pct(days, max_days))
    if "schema" in p or "null" in p:
        schema = metrics.get("schema", {})
        # Prefer the worst null-rate column; if no nulls, fall back to duplicates.
        worst_col, worst_pct, worst_count = None, 0.0, 0
        for col, st in schema.get("null_stats", {}).items():
            np_ = float(st.get("null_pct", 0))
            if np_ > worst_pct:
                worst_pct = np_
                worst_count = int(st.get("null_count", 0))
                worst_col = col
        if worst_col and worst_pct > 0:
            return (worst_count, total_rows, worst_pct)
        return (
            int(schema.get("duplicate_count", 0)),
            total_rows,
            float(schema.get("duplicate_pct", 0.0)),
        )
    if "distribution" in p or "outlier" in p:
        dist = metrics.get("distribution", {}).get("outlier_stats", {})
        worst = max(
            dist.items(),
            key=lambda kv: kv[1].get("outlier_count", 0),
            default=None,
        )
        if worst:
            _, st = worst
            return (
                int(st.get("outlier_count", 0)),
                total_rows,
                float(st.get("outlier_pct", 0.0)),
            )
        return (0, total_rows, 0.0)
    if "lineage" in p or "drift" in p:
        drift = metrics.get("lineage", {}).get("drift_results", {})
        with_drift = sum(1 for v in drift.values() if v.get("drift_detected"))
        total_cols = len(drift) or 1
        return (with_drift, total_cols, _pct(with_drift, total_cols))

    return (0, total_rows, 0.0)


def _metrics_for_incident(
    title: str, root_cause: str, metrics: Dict[str, Any]
) -> Tuple[int, int, float]:
    """Best-effort: map an RCA incident's title/root-cause keywords to a metric."""
    blob = (title + " " + root_cause).lower()
    total_rows = int(metrics.get("total_rows", 0))

    if "volume" in blob:
        vol = metrics.get("volume", {})
        return (
            int(vol.get("total_rows", 0)),
            int(vol.get("expected_rows", 0)),
            float(vol.get("volume_pct", 0.0)),
        )
    if "fresh" in blob or "latency" in blob or "stale" in blob:
        fresh = metrics.get("freshness", {})
        days = int(fresh.get("days_since_last_visit", 0))
        max_days = int(fresh.get("freshness_max_days", 1)) or 1
        return (days, max_days, _pct(days, max_days))
    if "outlier" in blob:
        dist = metrics.get("distribution", {}).get("outlier_stats", {})
        worst = max(
            dist.items(),
            key=lambda kv: kv[1].get("outlier_count", 0),
            default=None,
        )
        if worst:
            _, st = worst
            return (
                int(st.get("outlier_count", 0)),
                total_rows,
                float(st.get("outlier_pct", 0.0)),
            )
    if "drift" in blob or "distribution" in blob:
        drift = metrics.get("lineage", {}).get("drift_results", {})
        with_drift = sum(1 for v in drift.values() if v.get("drift_detected"))
        total_cols = len(drift) or 1
        return (with_drift, total_cols, _pct(with_drift, total_cols))
    if "duplicate" in blob:
        schema = metrics.get("schema", {})
        return (
            int(schema.get("duplicate_count", 0)),
            total_rows,
            float(schema.get("duplicate_pct", 0.0)),
        )
    if "null" in blob or "missing" in blob:
        schema = metrics.get("schema", {})
        worst_col, worst_pct, worst_count = None, 0.0, 0
        for col, st in schema.get("null_stats", {}).items():
            np_ = float(st.get("null_pct", 0))
            if np_ > worst_pct:
                worst_pct = np_
                worst_count = int(st.get("null_count", 0))
                worst_col = col
        if worst_col:
            return (worst_count, total_rows, worst_pct)

    return (0, 0, 0.0)


def _evidence_from_metrics(metrics: Dict[str, Any]) -> str:
    """Compose a concise factual evidence string straight from sanitized metrics."""
    vol = metrics.get("volume", {})
    fresh = metrics.get("freshness", {})
    schema = metrics.get("schema", {})
    dist = metrics.get("distribution", {}).get("outlier_stats", {})
    lineage = metrics.get("lineage", {}).get("drift_results", {})

    parts: List[str] = []
    parts.append(
        f"Volume: {vol.get('total_rows', 0)}/{vol.get('expected_rows', 0)} "
        f"({vol.get('volume_pct', 0)}%)"
    )
    parts.append(
        f"Freshness: {fresh.get('days_since_last_visit', 0)} days since last visit "
        f"(max {fresh.get('freshness_max_days', 7)}d)"
    )
    parts.append(
        f"Duplicates: {schema.get('duplicate_count', 0)} "
        f"({schema.get('duplicate_pct', 0)}%)"
    )
    for col, st in dist.items():
        if st.get("outlier_count", 0) > 0:
            parts.append(
                f"Outliers in {col}: {st.get('outlier_count')} "
                f"({st.get('outlier_pct', 0)}%)"
            )
    for col, st in lineage.items():
        if st.get("drift_detected"):
            parts.append(f"Drift in {col}: p={st.get('p_value', 0)}")
    return " | ".join(parts)
