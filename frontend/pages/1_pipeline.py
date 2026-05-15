"""
1_pipeline.py
Pipeline trigger and live progress tracking page.
"""

import time
import httpx
import streamlit as st

st.set_page_config(
    page_title="Pipeline | Clinical Observability",
    page_icon="🔬",
    layout="wide",
)

BACKEND_URL = st.session_state.get("backend_url", "http://localhost:8000")

# ── Helpers ───────────────────────────────────────────────────────────────────

def trigger_pipeline() -> dict:
    try:
        resp = httpx.post(f"{BACKEND_URL}/pipeline/run", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", str(exc))
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


def poll_status(run_id: str) -> dict:
    try:
        resp = httpx.get(f"{BACKEND_URL}/pipeline/status/{run_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def get_history() -> list:
    try:
        resp = httpx.get(f"{BACKEND_URL}/pipeline/history", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


STAGE_LABELS = {
    "initializing":          ("Initializing pipeline...", 0),
    "input_discovery":       ("Discovering CSV file", 10),
    "entry_validation":      ("Validating schema and freshness", 20),
    "preprocessing":         ("Running Pandas analysis + ETL log generation", 40),
    "pii_masking":           ("Applying PII/PHI masking (Presidio)", 60),
    "agent_pipeline":        ("AI Agents running...", 70),
    "agent_data_quality":    ("Data Quality Agent analyzing...", 72),
    "agent_log_analysis":    ("Log Analysis Agent reading ETL log...", 76),
    "agent_rca":             ("RCA Agent cross-correlating findings...", 82),
    "agent_recommendation":  ("Recommendation Agent drafting steps...", 88),
    "agent_compliance":      ("Compliance Agent reviewing...", 93),
    "saving_report":         ("Saving incident report draft", 96),
    "awaiting_human_review": ("Awaiting human review...", 99),
}

STATUS_STEPS = [
    ("input_discovery",     "📁 Input Discovery"),
    ("entry_validation",    "✅ Entry Validation"),
    ("preprocessing",       "⚙️ Preprocessing"),
    ("pii_masking",         "🔒 PII/PHI Masking"),
    ("agent_pipeline",      "🤖 AI Agents"),
    ("saving_report",       "📄 Incident Report"),
    ("awaiting_human_review","👤 Awaiting Review"),
]

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🔬 Clinical Trial Data Pipeline")
st.markdown("Trigger the observability pipeline. The CSV is read from `data/clinical/clinical_trial_data.csv`.")
st.markdown("---")

# ── Dataset info card ─────────────────────────────────────────────────────────
with st.expander("📁 Dataset Information", expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric("File", "clinical_trial_data.csv")
    col2.metric("Location", "data/clinical/")
    col3.metric("Expected Rows", "500")
    st.caption("The CSV file must be pre-placed in the `data/clinical/` directory on the server.")

# ── Pipeline history ──────────────────────────────────────────────────────────
with st.expander("📜 Previous Runs", expanded=False):
    history = get_history()
    if history:
        for run in history[:5]:
            status_icon = {
                "approved": "🟢", "pending_review": "🟡",
                "rejected": "🔴", "error": "🔴", "running": "🔵",
            }.get(run["status"], "⚪")
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            col1.caption(run["run_id"][:16] + "...")
            col2.caption(run.get("started_at", "")[:19])
            col3.caption(f"{status_icon} {run['status']}")
            if run["status"] == "approved" and col4.button("Load", key=run["run_id"]):
                st.session_state.run_id = run["run_id"]
                st.session_state.pipeline_status = "approved"
                st.switch_page("pages/3_dashboard.py")
    else:
        st.caption("No previous runs found.")

st.markdown("---")

# ── Pipeline control ──────────────────────────────────────────────────────────
current_status = st.session_state.get("pipeline_status")
current_run_id = st.session_state.get("run_id")

col_btn, col_status = st.columns([1, 3])

with col_btn:
    run_button_disabled = current_status == "running"
    if st.button(
        "▶ Run Pipeline",
        type="primary",
        disabled=run_button_disabled,
        use_container_width=True,
        help="Trigger the full observability pipeline",
    ):
        with st.spinner("Starting pipeline..."):
            result = trigger_pipeline()

        if "error" in result:
            st.error(f"❌ Failed to start: {result['error']}")
        else:
            st.session_state.run_id = result["run_id"]
            st.session_state.pipeline_status = "running"
            st.rerun()

with col_status:
    if current_run_id:
        st.info(f"**Run ID:** `{current_run_id}`")

# ── Live progress display ─────────────────────────────────────────────────────
if current_run_id and current_status in ("running", "pending_review", "approved",
                                          "rejected", "error", "validation_failed"):
    st.markdown("### Pipeline Progress")

    status_data = poll_status(current_run_id)

    if "error" not in status_data:
        live_status = status_data.get("status", current_status)
        current_stage = status_data.get("current_stage", "")
        progress_pct = status_data.get("progress_pct", 0)
        errors = status_data.get("errors", [])
        warnings = status_data.get("warnings", [])

        st.session_state.pipeline_status = live_status

        # Progress bar
        st.progress(progress_pct / 100, text=f"{progress_pct}% — {current_stage}")

        # Step indicators
        completed_stages = set()
        all_stages = [s[0] for s in STATUS_STEPS]
        try:
            current_idx = all_stages.index(current_stage)
            completed_stages = set(all_stages[:current_idx])
        except ValueError:
            pass

        step_cols = st.columns(len(STATUS_STEPS))
        for i, (stage_key, stage_label) in enumerate(STATUS_STEPS):
            with step_cols[i]:
                if live_status in ("error", "validation_failed") and stage_key == current_stage:
                    st.markdown(f"❌  \n{stage_label}")
                elif stage_key in completed_stages or live_status in ("pending_review", "approved"):
                    st.markdown(f"✅  \n{stage_label}")
                elif stage_key == current_stage and live_status == "running":
                    st.markdown(f"⏳  \n{stage_label}")
                else:
                    st.markdown(f"⬜  \n{stage_label}")

        # Warnings
        if warnings:
            with st.expander(f"⚠️ {len(warnings)} Validation Warning(s)", expanded=True):
                for w in warnings:
                    st.warning(w)

        # Errors
        if errors:
            for e in errors:
                st.error(f"❌ {e}")

        # Status-specific banners
        if live_status == "pending_review":
            st.success("✅ **Pipeline complete!** The AI incident report is ready for review.")
            st.balloons()
            if st.button("📋 Go to Review Page", type="primary"):
                st.switch_page("pages/2_review.py")

        elif live_status == "approved":
            st.success("🎉 Report approved! Dashboard is unlocked.")
            if st.button("📊 Go to Dashboard", type="primary"):
                st.switch_page("pages/3_dashboard.py")

        elif live_status == "rejected":
            st.error("❌ Report was rejected. Please fix the issues and re-run the pipeline.")

        elif live_status in ("error", "validation_failed"):
            st.error("❌ Pipeline failed. Check the errors above.")

        # Auto-refresh while running
        if live_status == "running":
            time.sleep(2)
            st.rerun()
