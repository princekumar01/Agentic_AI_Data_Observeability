"""
3_dashboard.py
Clinical Analytics Dashboard — rendered after HITL approval.
Shows Plotly charts, agent findings, incident report, and audit trail.
"""

import html
import json
import httpx
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Dashboard | Clinical Observability",
    page_icon="📊",
    layout="wide",
)

BACKEND_URL = st.session_state.get("backend_url", "http://localhost:8000")


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_dashboard(run_id: str) -> dict:
    """Cache the dashboard payload for 5 minutes per run_id. Streamlit reruns
    the whole script on every interaction; without caching, this would refire
    on every tab click, expander open, etc."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/dashboard/{run_id}", timeout=20)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", str(exc))
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


@st.cache_data(ttl=300, show_spinner=False)
def load_audit_trail(run_id: str, runs_directory: str) -> dict:
    """Read audit_trail.json from disk once per run_id, not on every rerun."""
    import os, json
    audit_path = os.path.join(runs_directory, run_id, "audit_trail.json")
    if not os.path.exists(audit_path):
        return {}
    with open(audit_path) as f:
        return json.load(f)


def _health_color(score: int) -> str:
    if score >= 80:
        return "normal"
    elif score >= 60:
        return "off"
    return "inverse"


def _pillar_badge(ok: bool, label: str) -> str:
    icon = "✅" if ok else "🔴"
    return f"{icon} {label}"


def _finding_class(value: str) -> str:
    upper = value.upper()
    if upper in ("OK", "CLEAN", "COMPLETE", "ALIGNED"):
        return "finding-ok"
    if upper in ("WARNING", "MEDIUM", "DEGRADED", "NEEDS REVISION"):
        return "finding-warn"
    if upper in ("ANOMALY", "HIGH", "RETURN FOR REVISION"):
        return "finding-bad"
    return ""


@st.cache_data(show_spinner=False)
def _build_agent_finding_html(content: str) -> str:
    """Build the HTML for an agent finding once and cache it.
    Tabs render content for ALL 5 agents on every rerun (Streamlit doesn't
    skip hidden tabs), so caching the string-building step saves ~5× work."""
    html_parts = ['<div class="agent-finding">']
    list_open = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            if list_open:
                html_parts.append("</ul>")
                list_open = False
            continue
        if line.startswith("- "):
            if not list_open:
                html_parts.append("<ul>")
                list_open = True
            html_parts.append(f"<li>{html.escape(line[2:])}</li>")
        elif ":" in line and line.split(":", 1)[0].isupper():
            if list_open:
                html_parts.append("</ul>")
                list_open = False
            label, value = line.split(":", 1)
            html_parts.append(
                f'<div class="finding-row"><span>{html.escape(label)}</span>'
                f'<strong class="{_finding_class(value.strip())}">{html.escape(value.strip())}</strong></div>'
            )
        else:
            html_parts.append(f"<p>{html.escape(line)}</p>")
    if list_open:
        html_parts.append("</ul>")
    html_parts.append("</div>")
    return "".join(html_parts)


def _render_agent_finding(content: str) -> None:
    st.markdown(_build_agent_finding_html(content), unsafe_allow_html=True)


st.markdown(
    """
    <style>
    .agent-finding {
        padding: .8rem .9rem;
        border: 1px solid #334155;
        border-radius: 12px;
        background: #0f172a;
        color: #e2e8f0;
    }
    .agent-finding p { margin: .3rem 0; line-height: 1.45; color: #e2e8f0; }
    .agent-finding ul { margin: .3rem 0 .55rem 1.1rem; color: #e2e8f0; }
    .agent-finding li { margin: .15rem 0; color: #e2e8f0; }
    .finding-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin: .3rem 0;
        padding: .5rem .65rem;
        border: 1px solid #334155;
        border-radius: 10px;
        background: #111827;
        color: #e2e8f0;
    }
    .finding-row span { font-weight: 600; color: #cbd5e1; }
    .finding-row strong { color: #f8fafc; }
    .finding-ok { color: #34d399; }
    .finding-warn { color: #fbbf24; }
    .finding-bad { color: #f87171; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Gate: require approved run ────────────────────────────────────────────────
st.title("📊 Clinical Analytics Dashboard")
st.markdown("Post-approval clinical trial data observability report.")
st.markdown("---")

run_id = st.session_state.get("run_id")
pipeline_status = st.session_state.get("pipeline_status")

if not run_id:
    st.warning("⚠️ No active run found. Please run the pipeline first.")
    if st.button("▶ Go to Pipeline"):
        st.switch_page("pages/1_pipeline.py")
    st.stop()

if pipeline_status != "approved":
    st.info(
        f"🔒 Dashboard is locked. Current run status: **`{pipeline_status}`**\n\n"
        f"The dashboard unlocks after a Clinical Data Manager approves the report."
    )
    col1, col2 = st.columns(2)
    if col1.button("📋 Go to Review", use_container_width=True):
        st.switch_page("pages/2_review.py")
    if col2.button("🔄 Refresh Status", use_container_width=True):
        st.rerun()
    st.stop()

# ── Load dashboard data ───────────────────────────────────────────────────────
with st.spinner("Loading dashboard data..."):
    data = fetch_dashboard(run_id)

if "error" in data:
    st.error(f"❌ {data['error']}")
    st.stop()

metrics      = data.get("metrics", {})
chart_data   = data.get("pillar_chart_data", {})
agent_findings = data.get("agent_findings", {})
audit_summary  = data.get("audit_summary", {})
incident_report_md = data.get("incident_report_md", "")
health_score = data.get("health_score", 0)

dist   = chart_data.get("distribution", {})
vol    = chart_data.get("volume", {})
schema_data = chart_data.get("schema", {})
freshness   = chart_data.get("freshness", {})
lineage     = chart_data.get("lineage", {})

# ══════════════════════════════════════════════════════════════════════════════
# ROW 1 — KPI Cards
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📌 Key Performance Indicators")
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric(
    "Health Score",
    f"{health_score}/100",
    delta=None,
    help="Overall pipeline health. 100 = no anomalies.",
)
vol_delta_val = vol.get('volume_delta_pct', 0)
vol_delta_str = "On target" if vol_delta_val == 0 else f"{vol_delta_val:.1f}% vs expected"

k2.metric(
    "Patient Records",
    vol.get("row_count", 0),
    delta=vol_delta_str,
    delta_color="inverse" if vol.get("volume_anomaly") else "normal",
)
k3.metric(
    "Anomalies Detected",
    metrics.get("anomaly_count", 0),
    delta=None,
    help="Total anomalies flagged across all pillars.",
)
k4.metric(
    "Critical Events",
    f"{dist.get('critical_event_pct', 0):.1f}%",
    delta=None,
    help="Percentage of patients with Critical severity.",
)

drift_results = dist.get("drift_detection", {})
any_drift = any(v.get("drift_detected") for v in drift_results.values())
k5.metric("Drift Status", "⚠️ Drift" if any_drift else "✅ Stable")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 2 — Pillar Status Indicators
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🏛 Observability Pillar Status")

p1, p2, p3, p4, p5 = st.columns(5)

freshness_ok = freshness.get("freshness_ok", True)
volume_ok    = not vol.get("volume_anomaly", False)
schema_ok    = (
    len(schema_data.get("missing_columns", [])) == 0
    and all(check.get("passed", False) for check in schema_data.get("dtype_checks", {}).values())
    and schema_data.get("duplicate_patient_ids", 0) == 0
)
# Distribution pillar is healthy only if BOTH drift and outlier checks are clean.
# Previously this only checked drift, which meant 12 severe-hyperglycemia outliers
# could be flagged elsewhere but the pillar card still showed green — confusing
# reviewers because the Review page (which the LLM writes) called it an ANOMALY.
glucose_outliers = dist.get("glucose_level", {}).get("outlier_count", 0)
age_outliers     = dist.get("age", {}).get("outlier_count", 0)
clinical_alerts  = (dist.get("glucose_level", {}).get("clinical_alert_count", 0)
                    + dist.get("age", {}).get("clinical_alert_count", 0))
dist_ok      = not any_drift and glucose_outliers == 0 and age_outliers == 0
dist_detail  = "KS drift test"
if clinical_alerts > 0:
    dist_detail = f"{clinical_alerts} clinical alert(s)"
elif glucose_outliers + age_outliers > 0:
    dist_detail = f"{glucose_outliers + age_outliers} outlier(s)"
elif any_drift:
    dist_detail = "Drift detected"
lineage_ok   = lineage.get("error_count", 0) == 0 and lineage.get("warning_count", 0) == 0

for col, label, ok, detail in [
    (p1, "🕐 Freshness",    freshness_ok, f"Last visit: {freshness.get('most_recent_visit_date','N/A')}"),
    (p2, "📦 Volume",       volume_ok,    f"Δ {vol.get('volume_delta_pct',0):.1f}%"),
    (p3, "🗂 Schema (10/10 validated)", schema_ok, "All columns present"),
    (p4, "📈 Distribution", dist_ok,      dist_detail),
    (p5, "🔗 Lineage",      lineage_ok,   f"{lineage.get('warning_count',0)} warnings"),
]:
    with col:
        if ok:
            st.success(f"**{label}**\n\n{detail}")
        elif label == "🔗 Lineage" and lineage.get("error_count", 0) == 0:
            st.warning(f"**{label}**\n\n{detail}")
        else:
            st.error(f"**{label}**\n\n{detail}")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 3 — Distribution Charts
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Distribution Analysis")
c1, c2 = st.columns(2)

with c1:
    # Severity Pie Chart
    sev_counts = dist.get("severity_counts", {})
    if sev_counts:
        fig_sev = px.pie(
            names=list(sev_counts.keys()),
            values=list(sev_counts.values()),
            title="Patient Severity Distribution",
            color=list(sev_counts.keys()),
            color_discrete_map={
                "Low": "#2ecc71",
                "Medium": "#f39c12",
                "High": "#e67e22",
                "Critical": "#e74c3c",
            },
            hole=0.35,
        )
        fig_sev.update_traces(textinfo="percent+label")
        fig_sev.update_layout(height=360, margin=dict(t=40, b=10, l=10, r=10))
        st.plotly_chart(fig_sev, use_container_width=True)
    else:
        st.info("Severity distribution data not available.")

with c2:
    # Glucose Level Distribution (box + outlier bounds)
    glucose_stats = dist.get("glucose_level", {})
    if glucose_stats:
        fig_gluc = go.Figure()
        fig_gluc.add_trace(go.Box(
            q1=[glucose_stats.get("q1", 0)],
            median=[glucose_stats.get("mean", 0)],
            q3=[glucose_stats.get("q3", 0)],
            lowerfence=[glucose_stats.get("min", 0)],
            upperfence=[glucose_stats.get("max", 0)],
            name="Glucose Level",
            marker_color="#3498db",
            boxmean=True,
        ))
        fig_gluc.add_hline(
            y=glucose_stats.get("outlier_lower_bound", 0),
            line_dash="dash", line_color="red",
            annotation_text="Lower outlier bound",
            annotation_position="bottom right",
        )
        fig_gluc.add_hline(
            y=glucose_stats.get("outlier_upper_bound", 0),
            line_dash="dash", line_color="red",
            annotation_text="Upper outlier bound",
            annotation_position="top right",
        )
        fig_gluc.update_layout(
            title="Glucose Level Distribution",
            yaxis_title="Glucose Level (mg/dL)",
            height=360,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_gluc, use_container_width=True)
    else:
        st.info("Glucose level data not available.")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 4 — Side Effects + Null Report
# ══════════════════════════════════════════════════════════════════════════════
c3, c4 = st.columns(2)

with c3:
    side_effects = dist.get("side_effect_counts", {})
    if side_effects:
        sorted_se = dict(sorted(side_effects.items(), key=lambda x: x[1], reverse=True)[:10])
        fig_se = px.bar(
            x=list(sorted_se.values()),
            y=list(sorted_se.keys()),
            orientation="h",
            title="Top Side Effects by Frequency",
            labels={"x": "Count", "y": "Side Effect"},
            color=list(sorted_se.values()),
            color_continuous_scale="Reds",
        )
        fig_se.update_layout(
            height=360,
            margin=dict(t=40, b=10, l=10, r=10),
            showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_se, use_container_width=True)
    else:
        st.info("Side effect data not available.")

with c4:
    null_report = schema_data.get("null_report", {})
    if null_report:
        cols_list = list(null_report.keys())
        null_pcts = [null_report[c].get("null_pct", 0) for c in cols_list]
        colors = ["#e74c3c" if p > 5 else "#2ecc71" for p in null_pcts]

        fig_null = go.Figure(go.Bar(
            x=cols_list,
            y=null_pcts,
            marker_color=colors,
            text=[f"{p:.1f}%" for p in null_pcts],
            textposition="auto",
        ))
        fig_null.add_hline(
            y=5, line_dash="dash", line_color="orange",
            annotation_text="Threshold (5%)",
        )
        fig_null.update_layout(
            title="Null Rate by Column (%)",
            xaxis_title="Column",
            yaxis_title="Null %",
            height=360,
            margin=dict(t=40, b=10, l=10, r=10),
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig_null, use_container_width=True)
    else:
        st.info("Null report not available.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 5 — Volume + Age Distribution
# ══════════════════════════════════════════════════════════════════════════════
c5, c6 = st.columns(2)

with c5:
    # Volume gauge
    row_count   = vol.get("row_count", 0)
    expected    = vol.get("expected_row_count", 500)
    delta_pct   = vol.get("volume_delta_pct", 0)

    fig_vol = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=row_count,
        delta={"reference": expected, "valueformat": ".0f"},
        title={"text": "Patient Records (vs Expected)"},
        gauge={
            "axis": {"range": [0, max(expected * 1.2, row_count * 1.1)]},
            "bar": {"color": "#3498db"},
            "steps": [
                {"range": [0, expected * 0.9],  "color": "#fadbd8"},
                {"range": [expected * 0.9, expected * 1.1], "color": "#d5f5e3"},
                {"range": [expected * 1.1, expected * 1.2], "color": "#fdebd0"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 3},
                "thickness": 0.75,
                "value": expected,
            },
        },
    ))
    fig_vol.update_layout(height=320, margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig_vol, use_container_width=True)

with c6:
    age_stats = dist.get("age", {})
    if age_stats:
        fig_age = go.Figure()
        fig_age.add_trace(go.Box(
            q1=[age_stats.get("q1", 0)],
            median=[age_stats.get("mean", 0)],
            q3=[age_stats.get("q3", 0)],
            lowerfence=[age_stats.get("min", 0)],
            upperfence=[age_stats.get("max", 0)],
            name="Patient Age",
            marker_color="#9b59b6",
            boxmean=True,
        ))
        fig_age.update_layout(
            title="Patient Age Distribution",
            yaxis_title="Age (years)",
            height=320,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_age, use_container_width=True)
    else:
        st.info("Age distribution data not available.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 6 — Drift Detection Table
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🔬 Drift Detection (KS-Test vs Baseline)")

if drift_results:
    drift_rows = []
    for col_name, d in drift_results.items():
        status = "🔴 DRIFT DETECTED" if d.get("drift_detected") else "✅ Stable"
        drift_rows.append({
            "Column": col_name,
            "KS Statistic": d.get("ks_statistic", "N/A"),
            "p-value": d.get("p_value", "N/A"),
            "Threshold": 0.05,
            "Status": status,
        })
    st.dataframe(
        drift_rows,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No drift detection results available.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 7 — Dtype Checks Table
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🗂 Schema Validation Results")
dtype_checks = schema_data.get("dtype_checks", {})
phi_dropped_cols = set(schema_data.get("phi_dropped_columns", []))
if dtype_checks:
    dtype_rows = []
    for col_name, check in dtype_checks.items():
        is_phi = col_name in phi_dropped_cols
        passed = check.get("passed", False)
        if is_phi:
            status_str = "🛡 PHI Masked (by design)" if passed else "❌ PHI Leak"
            expected_str = "PHI — must be removed"
            actual_str = "✓ Removed" if passed else "⚠ Still present"
        else:
            status_str = "✅ Pass" if passed else "❌ Fail"
            expected_str = check.get("expected", "")
            actual_str = check.get("actual", "")
        dtype_rows.append({
            "Column": col_name,
            "Expected Type": expected_str,
            "Actual Type": actual_str,
            "Status": status_str,
        })
    st.dataframe(dtype_rows, use_container_width=True, hide_index=True)

dup_count = schema_data.get("duplicate_patient_ids", 0)
if dup_count > 0:
    st.error(f"⚠️ **{dup_count} duplicate patient_id(s) detected** in this dataset.")
else:
    st.success("✅ No duplicate patient IDs detected.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 8 — Agent Findings Tabs
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🤖 AI Agent Findings")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Data Quality",
    "📋 Log Analysis",
    "🔎 Root Cause",
    "💡 Recommendations",
    "⚖️ Compliance",
])

agent_labels = {
    "data_quality":   tab1,
    "log_analysis":   tab2,
    "rca":            tab3,
    "recommendation": tab4,
    "compliance":     tab5,
}

for key, tab in agent_labels.items():
    with tab:
        content = agent_findings.get(key, "")
        if content:
            _render_agent_finding(content)
        else:
            st.info("Agent findings not available for this run.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 9 — Incident Report
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📄 Approved Incident Report")

with st.expander("View Full Report", expanded=False):
    if incident_report_md:
        st.markdown(incident_report_md)
    else:
        st.info("Incident report not available.")

if incident_report_md:
    st.download_button(
        label="⬇️ Download Incident Report (.md)",
        data=incident_report_md.encode("utf-8"),
        file_name=f"incident_report_{run_id[:8]}.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROW 10 — Audit Trail
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📜 Audit Trail (FDA 21 CFR Part 11)")

# Summary metrics
a1, a2, a3, a4 = st.columns(4)
a1.metric("Total Audit Entries", audit_summary.get("total_entries", 0))
a2.metric("Agent LLM Calls", audit_summary.get("agent_calls", 0))
a3.metric("Approved By", audit_summary.get("reviewer_id") or "N/A")
a4.metric("Approved At", (audit_summary.get("pipeline_approved_at") or "N/A")[:19])

with st.expander("📋 View Full Audit Log", expanded=False):
    try:
        import yaml, json
        with open("config.yaml") as f:
            cfg = yaml.safe_load(f)
        audit_data = load_audit_trail(run_id, cfg["output"]["runs_directory"])
        if audit_data:
            entries = audit_data.get("entries", [])
            table_rows = [
                {
                    "ID": e.get("entry_id"),
                    "Timestamp": e.get("timestamp", "")[:19],
                    "Stage": e.get("stage", ""),
                    "Event Type": e.get("event_type", ""),
                    "Agent": e.get("agent") or "—",
                }
                for e in entries
            ]
            if table_rows:
                st.dataframe(table_rows, use_container_width=True, hide_index=True)

            st.download_button(
                label="⬇️ Download Full Audit Trail (.json)",
                data=json.dumps(audit_data, indent=2, default=str).encode("utf-8"),
                file_name=f"audit_trail_{run_id[:8]}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.warning("Audit trail file not found on disk.")
    except Exception as exc:
        st.warning(f"Could not load audit trail: {exc}")

st.markdown("---")
st.caption(
    f"**Run ID:** `{run_id}` | "
    f"**Pipeline Started:** {audit_summary.get('pipeline_started_at', 'N/A')[:19]} | "
    f"**Approved:** {(audit_summary.get('pipeline_approved_at') or 'N/A')[:19]} | "
    f"Clinical Trial Observability v1.0"
)
