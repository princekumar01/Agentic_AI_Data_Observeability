"""
app.py
Streamlit application entry point.
Run with: streamlit run frontend/app.py --server.port 8501
"""

import streamlit as st

st.set_page_config(
    page_title="Clinical Trial Observability",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global session state defaults ────────────────────────────────────────────
if "run_id" not in st.session_state:
    st.session_state.run_id = None
if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = None
if "backend_url" not in st.session_state:
    st.session_state.backend_url = "http://localhost:8000"
if "validation_warnings" not in st.session_state:
    st.session_state.validation_warnings = []

# ── Sidebar navigation info ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital.png", width=60)
    st.title("Clinical Trial\nObservability")
    st.markdown("---")
    st.markdown("**Agentic AI Data Pipeline Monitor**")
    st.markdown("*FDA 21 CFR Part 11 Compliant*")
    st.markdown("---")

    if st.session_state.run_id:
        st.markdown(f"**Active Run:**")
        st.code(st.session_state.run_id[:8] + "...", language=None)

        status = st.session_state.pipeline_status or "unknown"
        status_colors = {
            "running": "🔵",
            "pending_review": "🟡",
            "approved": "🟢",
            "rejected": "🔴",
            "error": "🔴",
            "validation_failed": "🔴",
        }
        icon = status_colors.get(status, "⚪")
        st.markdown(f"**Status:** {icon} `{status}`")
    else:
        st.markdown("*No active run*")

    st.markdown("---")
    st.markdown("**Navigation**")
    st.page_link("pages/1_pipeline.py", label="▶ Pipeline", icon="🔬")
    st.page_link("pages/2_review.py", label="🔍 Review", icon="📋")
    st.page_link("pages/3_dashboard.py", label="📊 Dashboard", icon="📈")
    st.markdown("---")
    st.caption("v1.0.0 | Life Sciences POC")

# ── Landing page ─────────────────────────────────────────────────────────────
st.title("🏥 Clinical Trial AI Data Observability")
st.markdown(
    """
    **Agentic AI-powered monitoring for clinical trial data pipelines.**

    This system automatically monitors your clinical trial data across
    **5 observability pillars** and uses specialized AI agents to detect
    anomalies, investigate root causes, and generate compliance-ready incident reports.
    """
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**🔬 Step 1: Run Pipeline**\n\nNavigate to the Pipeline page and click Run to start analysis.")
with col2:
    st.warning("**📋 Step 2: Review Report**\n\nA Clinical Data Manager reviews and approves the AI-generated report.")
with col3:
    st.success("**📊 Step 3: View Dashboard**\n\nExplore analytics, agent findings, and download the approved report.")

st.markdown("---")
st.markdown(
    """
    | Pillar | What is monitored |
    |--------|------------------|
    | 🕐 Freshness | File age and most recent visit date |
    | 📦 Volume | Row count vs expected patient count |
    | 🗂 Schema | Column presence and data types |
    | 📈 Distribution | Outliers, drift detection (KS-test) |
    | 🔗 Lineage | ETL log correlation with anomalies |
    """
)
