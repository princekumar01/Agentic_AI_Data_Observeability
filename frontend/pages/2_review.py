"""
2_review.py
Human-in-the-Loop (HITL) review page.
Clinical Data Manager reads the AI-generated report and approves or rejects it.
The dashboard is locked until a run is approved here.
"""

import httpx
import streamlit as st

st.set_page_config(
    page_title="Review | Clinical Observability",
    page_icon="📋",
    layout="wide",
)

BACKEND_URL = st.session_state.get("backend_url", "http://localhost:8000")


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_review_payload(run_id: str) -> dict:
    try:
        resp = httpx.get(f"{BACKEND_URL}/review/{run_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": exc.response.json().get("detail", str(exc))}
    except Exception as exc:
        return {"error": str(exc)}


def approve_report(run_id: str, reviewer_id: str, notes: str) -> dict:
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/review/approve",
            json={"run_id": run_id, "reviewer_id": reviewer_id, "notes": notes},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": exc.response.json().get("detail", str(exc))}
    except Exception as exc:
        return {"error": str(exc)}


def reject_report(run_id: str, reviewer_id: str, notes: str) -> dict:
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/review/reject",
            json={"run_id": run_id, "reviewer_id": reviewer_id, "notes": notes},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": exc.response.json().get("detail", str(exc))}
    except Exception as exc:
        return {"error": str(exc)}


def _pillar_icon(ok: bool) -> str:
    return "🟢" if ok else "🔴"


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📋 Incident Report Review")
st.markdown("**Human-in-the-Loop Gate** — Review the AI-generated report before it is finalized.")
st.markdown("---")

run_id = st.session_state.get("run_id")

if not run_id:
    st.warning("⚠️ No active pipeline run found. Please run the pipeline first.")
    if st.button("▶ Go to Pipeline"):
        st.switch_page("pages/1_pipeline.py")
    st.stop()

pipeline_status = st.session_state.get("pipeline_status", "")

if pipeline_status not in ("pending_review", "approved", "rejected"):
    st.info(f"Pipeline is currently in state: `{pipeline_status}`. "
            f"The review page is available once the pipeline completes.")
    if st.button("🔄 Refresh"):
        st.rerun()
    if st.button("← Back to Pipeline"):
        st.switch_page("pages/1_pipeline.py")
    st.stop()

# ── Load review payload ───────────────────────────────────────────────────────
with st.spinner("Loading incident report..."):
    payload = fetch_review_payload(run_id)

if "error" in payload:
    st.error(f"❌ {payload['error']}")
    st.stop()

run_id_display = run_id[:8] + "..."
st.caption(f"**Run ID:** `{run_id}` | **Status:** `{pipeline_status}`")

# ── Two-column layout ─────────────────────────────────────────────────────────
col_report, col_review = st.columns([6, 4], gap="large")

with col_report:
    st.subheader("📄 AI Incident Report Draft")

    # Metrics summary cards
    summary = payload.get("metrics_summary", {})
    health = summary.get("health_score", 0)
    anomaly_count = summary.get("anomaly_count", 0)
    pillar_statuses = summary.get("pillar_statuses", {})

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Health Score", f"{health}/100")
    m2.metric("Anomalies", anomaly_count)
    m3.metric("Freshness", _pillar_icon(pillar_statuses.get("freshness", True)))
    m4.metric("Volume", _pillar_icon(pillar_statuses.get("volume", True)))
    m5.metric("Schema", _pillar_icon(pillar_statuses.get("schema", True)))

    # Anomalies list
    anomalies = summary.get("anomalies_detected", [])
    if anomalies:
        st.warning(f"⚠️ Anomalies detected: `{'`, `'.join(anomalies)}`")

    # Compliance status badge
    compliance_status = payload.get("compliance_status", "UNKNOWN")
    if "APPROVED" in compliance_status:
        st.success(f"✅ Compliance Status: **{compliance_status}**")
    else:
        st.error(f"⚠️ Compliance Status: **{compliance_status}**")

    # Report content
    st.markdown("---")
    incident_report_md = payload.get("incident_report_md", "")
    with st.container(height=600):
        st.markdown(incident_report_md)

with col_review:
    st.subheader("✍️ Review Decision")

    # Already decided
    if pipeline_status == "approved":
        st.success("✅ This report has already been **APPROVED**.")
        if st.button("📊 View Dashboard", type="primary", use_container_width=True):
            st.switch_page("pages/3_dashboard.py")
        st.stop()

    if pipeline_status == "rejected":
        st.error("❌ This report was **REJECTED**.")
        if st.button("▶ Run Pipeline Again", use_container_width=True):
            st.switch_page("pages/1_pipeline.py")
        st.stop()

    # Review form
    st.markdown("""
    > **Instructions:** Read the full incident report carefully.
    > Verify the compliance status, check for any PHI/PII, and confirm
    > the recommendations are appropriate before approving.
    """)

    reviewer_id = st.text_input(
        "Reviewer ID *",
        placeholder="e.g. CDM_DR_SMITH",
        help="Your employee or clinical data manager ID (required)",
    )

    reviewer_notes = st.text_area(
        "Review Notes",
        placeholder="Add any observations or notes about this report...",
        height=120,
    )

    st.markdown("---")

    # Approve button
    approve_disabled = not reviewer_id.strip()
    if st.button(
        "✅ Approve Report",
        type="primary",
        disabled=approve_disabled,
        use_container_width=True,
        help="Approve this report — unlocks the clinical dashboard",
    ):
        with st.spinner("Recording approval..."):
            result = approve_report(run_id, reviewer_id, reviewer_notes)
        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            st.session_state.pipeline_status = "approved"
            st.success("✅ Report approved! Redirecting to dashboard...")
            st.balloons()
            st.switch_page("pages/3_dashboard.py")

    st.markdown("")

    # Reject button
    reject_notes = st.text_area(
        "Rejection Reason * (required to reject)",
        placeholder="Describe what needs to be corrected before re-running...",
        height=80,
        key="reject_notes",
    )

    reject_disabled = not reviewer_id.strip() or not reject_notes.strip()
    if st.button(
        "❌ Reject — Request Revision",
        disabled=reject_disabled,
        use_container_width=True,
        help="Reject this report — pipeline must be re-run",
    ):
        with st.spinner("Recording rejection..."):
            result = reject_report(run_id, reviewer_id, reject_notes)
        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            st.session_state.pipeline_status = "rejected"
            st.error("❌ Report rejected. The pipeline must be re-run.")
            st.switch_page("pages/1_pipeline.py")

    st.markdown("---")
    st.markdown(
        """
        <small>

        **Regulatory compliance note:**
        By approving this report, you confirm:
        - The content is accurate and complete
        - No PHI/PII is present in the report
        - The recommendations are appropriate for clinical context
        - This report meets GCP and FDA 21 CFR Part 11 standards

        </small>
        """,
        unsafe_allow_html=True,
    )
