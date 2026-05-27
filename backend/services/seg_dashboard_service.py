"""
backend/services/dashboard_service.py
All dummy data for the segregated and aggregated dashboard.
Replace dummy functions with real DB/file reads when integrating.
"""
from __future__ import annotations
from typing import Any, Dict, List

# ─── Dummy approved run list ──────────────────────────────────────────────────

APPROVED_RUNS = [
    {
        "run_id": "RUN-2026-0526-001",
        "started_at": "2026-05-26T14:18:00",
        "completed_at": "2026-05-26T14:26:42",
        "duration_seconds": 522,
        "records_processed": 500,
        "records_expected": 510,
        "status": "approved",
        "model": "claude-sonnet-4",
        "approved_at": "2026-05-26T14:32:00",
        "approved_by": "Dr. Priya Nair",
    }
]

# ─── Per-run dummy data ───────────────────────────────────────────────────────

RUN_DATA: Dict[str, Dict[str, Any]] = {
    "RUN-2026-0526-001": {
        "kpis": {
            "anomalies_detected": 17,
            "records_processed": 500,
            "compliance_score": 91,
        },
        "null_rate_by_column": [
            {"column": "patient_id",    "null_pct": 0.0,  "threshold": 5.0},
            {"column": "age",           "null_pct": 0.0,  "threshold": 5.0},
            {"column": "medication",    "null_pct": 0.2,  "threshold": 5.0},
            {"column": "blood_pressure","null_pct": 0.8,  "threshold": 5.0},
            {"column": "glucose_level", "null_pct": 2.4,  "threshold": 5.0},
            {"column": "side_effect",   "null_pct": 7.4,  "threshold": 5.0},
            {"column": "severity",      "null_pct": 0.0,  "threshold": 5.0},
            {"column": "visit_date",    "null_pct": 0.0,  "threshold": 5.0},
            {"column": "hospital_name", "null_pct": 0.0,  "threshold": 5.0},
        ],
        "severity_distribution": [
            {"severity": "Critical", "count": 3,  "pct": 17.6, "color": "#EF4444"},
            {"severity": "High",     "count": 5,  "pct": 29.4, "color": "#F59E0B"},
            {"severity": "Medium",   "count": 7,  "pct": 41.2, "color": "#3B82F6"},
            {"severity": "Low",      "count": 2,  "pct": 11.8, "color": "#10B981"},
        ],
        "records_vs_expected": {
            "actual": 500,
            "expected": 510,
            "gap": -10,
            "gap_pct": -2.0,
        },
        "agent_confidence": [
            {"agent": "Data Quality Agent",    "confidence": 88, "status": "Completed"},
            {"agent": "Log Analysis Agent",    "confidence": 76, "status": "Completed"},
            {"agent": "Root Cause Agent",      "confidence": 82, "status": "Completed"},
            {"agent": "Recommendation Agent", "confidence": 91, "status": "Completed"},
            {"agent": "Compliance Agent",      "confidence": 68, "status": "Completed"},
        ],
        "anomaly_summary": [
            {"severity": "Critical", "count": 3,  "description": "Null spike in side_effect field"},
            {"severity": "High",     "count": 5,  "description": "Blood pressure out-of-range values"},
            {"severity": "Medium",   "count": 7,  "description": "Glucose level distribution drift"},
            {"severity": "Low",      "count": 2,  "description": "Minor visit date inconsistency"},
        ],
        "token_usage": {
            "run_total_input":  24810,
            "run_total_output": 8340,
            "run_total":        33150,
            "estimated_cost":   0.0281,
            "model":            "claude-sonnet-4",
            "by_agent": [
                {"agent": "Data Quality Agent",    "tokens": 12580, "pct": 37.9},
                {"agent": "Log Analysis Agent",    "tokens": 6820,  "pct": 20.6},
                {"agent": "Root Cause Agent",      "tokens": 5640,  "pct": 17.0},
                {"agent": "Recommendation Agent", "tokens": 4520,  "pct": 13.6},
                {"agent": "Compliance Agent",      "tokens": 3590,  "pct": 10.8},
            ],
        },
        "observability_pillars": [
            {
                "key": "freshness",
                "label": "Freshness",
                "icon": "clock",
                "score": 74,
                "status": "warning",
                "detail": "Last visit: 2026-05-14",
                "color": "#F59E0B",
            },
            {
                "key": "schema",
                "label": "Schema",
                "icon": "layout",
                "score": 100,
                "status": "normal",
                "detail": "10/10 validated · All columns present",
                "color": "#10B981",
            },
            {
                "key": "volume",
                "label": "Volume",
                "icon": "database",
                "score": 98,
                "status": "normal",
                "detail": "Δ 0.0% from expected",
                "color": "#10B981",
            },
            {
                "key": "distribution",
                "label": "Distribution",
                "icon": "bar-chart",
                "score": 61,
                "status": "critical",
                "detail": "12 clinical alert(s)",
                "color": "#EF4444",
            },
            {
                "key": "lineage",
                "label": "Lineage",
                "icon": "git-branch",
                "score": 80,
                "status": "warning",
                "detail": "5 warnings",
                "color": "#F59E0B",
            },
        ],
        "agent_findings": {
            "data_quality": [
                {
                    "finding_type": "High Null Rate — side_effect",
                    "severity": "critical",
                    "confidence": 88,
                    "description": "7.4% null rate in side_effect column exceeds 5% threshold. Affects 37 patient records. Indicates possible data collection failure at source.",
                    "affected_field": "side_effect",
                    "recommendation": "Investigate data collection pipeline for side_effect field. Contact site coordinators to backfill missing entries.",
                },
                {
                    "finding_type": "Blood Pressure Out-of-Range",
                    "severity": "high",
                    "confidence": 82,
                    "description": "12 records with blood_pressure values outside clinically acceptable range (systolic >180 or <80). Requires clinical review.",
                    "affected_field": "blood_pressure",
                    "recommendation": "Flag affected records for clinical review. Verify measurement device calibration at relevant sites.",
                },
                {
                    "finding_type": "Glucose Distribution Drift",
                    "severity": "medium",
                    "confidence": 76,
                    "description": "Glucose level distribution shifted from baseline. Null rate at 2.4% — within threshold but trending upward.",
                    "affected_field": "glucose_level",
                    "recommendation": "Monitor glucose null rate in next run. Consider alert threshold lowering to 3% for this field.",
                },
            ],
            "log_analysis": [
                {
                    "finding_type": "Pipeline Stage Latency",
                    "severity": "medium",
                    "confidence": 79,
                    "description": "Data quality stage took 38% longer than baseline average (142s vs 103s). No data loss observed.",
                    "affected_field": None,
                    "recommendation": "Profile data quality agent for slow checks. Consider batching null-rate checks.",
                },
                {
                    "finding_type": "Retry on Compliance Agent",
                    "severity": "low",
                    "confidence": 71,
                    "description": "Compliance agent retried 2 times due to LLM timeout. Final result was successful.",
                    "affected_field": None,
                    "recommendation": "Increase LLM timeout from 30s to 45s for compliance agent.",
                },
            ],
            "rca": [
                {
                    "finding_type": "Root Cause: Null Spike in side_effect",
                    "severity": "critical",
                    "confidence": 85,
                    "description": "Root cause identified as upstream ETL failure at Hospital B site on 2026-05-14. Side effect data not collected for 37 records between 14:00–16:00.",
                    "affected_field": "side_effect",
                    "recommendation": "Coordinate with Hospital B to recover missing data. Add upstream ETL monitoring.",
                },
            ],
            "recommendation": [
                {
                    "finding_type": "Immediate: Backfill side_effect Data",
                    "severity": "critical",
                    "confidence": 91,
                    "description": "37 patient records missing side_effect values from Hospital B. Data recovery is possible from paper CRFs within 30-day window.",
                    "affected_field": "side_effect",
                    "recommendation": "Initiate data recovery procedure per SOP-DM-007. Assign data manager to Hospital B within 48h.",
                },
                {
                    "finding_type": "Short-term: Blood Pressure Validation Rule",
                    "severity": "high",
                    "confidence": 88,
                    "description": "Add automated range validation for blood_pressure field to catch out-of-range values at ingestion time.",
                    "affected_field": "blood_pressure",
                    "recommendation": "Implement validation rule: systolic 80–200 mmHg, diastolic 40–120 mmHg. Alert on violation.",
                },
                {
                    "finding_type": "Long-term: Real-time ETL Monitoring",
                    "severity": "medium",
                    "confidence": 84,
                    "description": "Current ETL pipeline lacks real-time health checks. 3 of 5 anomalies in this run were caused by ETL issues detectable earlier.",
                    "affected_field": None,
                    "recommendation": "Integrate ETL health checks with Kafka consumer lag monitoring. Set alerts for >500 lag.",
                },
            ],
            "compliance": [
                {
                    "finding_type": "ICH E6 GCP — Missing Adverse Event Data",
                    "severity": "critical",
                    "confidence": 72,
                    "description": "37 records missing side_effect field violates ICH E6 GCP Section 4.9.2 (Adverse Event reporting requirements). Must be resolved before data lock.",
                    "affected_field": "side_effect",
                    "recommendation": "Do not proceed to data lock until side_effect data recovered. Document deviation per SOPs.",
                },
                {
                    "finding_type": "21 CFR Part 11 — Audit Trail Gap",
                    "severity": "high",
                    "confidence": 68,
                    "description": "2 records modified without audit trail entry. Possible manual edit bypassed electronic record system.",
                    "affected_field": None,
                    "recommendation": "Review system access logs for 2026-05-14. Retrain staff on electronic data entry procedures.",
                },
            ],
        },
    },

    "RUN-2026-0525-003": {
        "kpis": {
            "anomalies_detected": 9,
            "critical_count": 1,
            "high_count": 2,
            "records_processed": 487,
            "records_expected": 500,
            "data_health_score": 91,
            "compliance_score": 96,
        },
        "null_rate_by_column": [
            {"column": "patient_id",    "null_pct": 0.0, "threshold": 5.0},
            {"column": "age",           "null_pct": 0.0, "threshold": 5.0},
            {"column": "medication",    "null_pct": 0.4, "threshold": 5.0},
            {"column": "blood_pressure","null_pct": 1.2, "threshold": 5.0},
            {"column": "glucose_level", "null_pct": 1.8, "threshold": 5.0},
            {"column": "side_effect",   "null_pct": 3.1, "threshold": 5.0},
            {"column": "severity",      "null_pct": 0.0, "threshold": 5.0},
            {"column": "visit_date",    "null_pct": 0.2, "threshold": 5.0},
            {"column": "hospital_name", "null_pct": 0.0, "threshold": 5.0},
        ],
        "severity_distribution": [
            {"severity": "Critical", "count": 1, "pct": 11.1, "color": "#EF4444"},
            {"severity": "High",     "count": 2, "pct": 22.2, "color": "#F59E0B"},
            {"severity": "Medium",   "count": 4, "pct": 44.4, "color": "#3B82F6"},
            {"severity": "Low",      "count": 2, "pct": 22.2, "color": "#10B981"},
        ],
        "records_vs_expected": {
            "actual": 487,
            "expected": 500,
            "gap": -13,
            "gap_pct": -2.6,
        },
        "agent_confidence": [
            {"agent": "Data Quality Agent",    "confidence": 92, "inferences": 28, "status": "Completed"},
            {"agent": "Log Analysis Agent",    "confidence": 84, "inferences": 17, "status": "Completed"},
            {"agent": "Root Cause Agent",      "confidence": 87, "inferences": 14, "status": "Completed"},
            {"agent": "Recommendation Agent", "confidence": 93, "inferences": 11, "status": "Completed"},
            {"agent": "Compliance Agent",      "confidence": 89, "inferences": 9,  "status": "Completed"},
        ],
        "anomaly_summary": [
            {"severity": "Critical", "count": 1, "description": "Duplicate patient_id detected"},
            {"severity": "High",     "count": 2, "description": "Visit date outside protocol window"},
            {"severity": "Medium",   "count": 4, "description": "Mild blood pressure variance"},
            {"severity": "Low",      "count": 2, "description": "Medication dosage rounding"},
        ],
        "token_usage": {
            "run_total_input":  21300,
            "run_total_output": 7100,
            "run_total":        28400,
            "estimated_cost":   0.0241,
            "model":            "claude-sonnet-4",
            "by_agent": [
                {"agent": "Data Quality Agent",    "tokens": 10800, "pct": 38.0},
                {"agent": "Log Analysis Agent",    "tokens": 5900,  "pct": 20.8},
                {"agent": "Root Cause Agent",      "tokens": 4700,  "pct": 16.5},
                {"agent": "Recommendation Agent", "tokens": 3900,  "pct": 13.7},
                {"agent": "Compliance Agent",      "tokens": 3100,  "pct": 10.9},
            ],
        },
        "observability_pillars": [
            {"key": "freshness",     "label": "Freshness",     "icon": "clock",      "score": 92, "status": "normal",   "detail": "Last visit: 2026-05-25", "color": "#10B981"},
            {"key": "schema",        "label": "Schema",        "icon": "layout",     "score": 100,"status": "normal",   "detail": "10/10 validated · All columns present", "color": "#10B981"},
            {"key": "volume",        "label": "Volume",        "icon": "database",   "score": 94, "status": "normal",   "detail": "Δ -2.6% from expected", "color": "#10B981"},
            {"key": "distribution",  "label": "Distribution",  "icon": "bar-chart",  "score": 78, "status": "warning",  "detail": "5 clinical alert(s)", "color": "#F59E0B"},
            {"key": "lineage",       "label": "Lineage",       "icon": "git-branch", "score": 95, "status": "normal",   "detail": "1 warning", "color": "#10B981"},
        ],
        "agent_findings": {
            "data_quality": [
                {
                    "finding_type": "Duplicate Patient ID",
                    "severity": "critical",
                    "confidence": 92,
                    "description": "1 duplicate patient_id detected (PT-0042 appears twice). Could indicate double enrollment or data entry error.",
                    "affected_field": "patient_id",
                    "recommendation": "Investigate PT-0042. Verify with site whether this is a data entry error or genuine duplicate enrollment.",
                },
            ],
            "log_analysis": [
                {
                    "finding_type": "Normal Pipeline Execution",
                    "severity": "low",
                    "confidence": 84,
                    "description": "All pipeline stages completed within expected time bounds. No retries or failures.",
                    "affected_field": None,
                    "recommendation": "No action required.",
                },
            ],
            "rca": [
                {
                    "finding_type": "Root Cause: Duplicate Entry",
                    "severity": "critical",
                    "confidence": 87,
                    "description": "Duplicate patient_id traced to manual data re-entry at Site A after system outage on 2026-05-24.",
                    "affected_field": "patient_id",
                    "recommendation": "Remove duplicate record after confirmation. Document in deviation log.",
                },
            ],
            "recommendation": [
                {
                    "finding_type": "Implement Unique ID Constraint",
                    "severity": "high",
                    "confidence": 93,
                    "description": "No database-level unique constraint on patient_id allows duplicates to be ingested.",
                    "affected_field": "patient_id",
                    "recommendation": "Add UNIQUE constraint on patient_id at ingestion layer. Reject duplicates at source.",
                },
            ],
            "compliance": [
                {
                    "finding_type": "Protocol Deviation — Visit Window",
                    "severity": "high",
                    "confidence": 89,
                    "description": "2 patients had visit dates outside the ±3 day protocol window. Must be documented as protocol deviations.",
                    "affected_field": "visit_date",
                    "recommendation": "Submit protocol deviation reports for affected patients per SOP-PD-002.",
                },
            ],
        },
    },

    "RUN-2026-0524-002": {
        "kpis": {
            "anomalies_detected": 5,
            "critical_count": 0,
            "high_count": 1,
            "records_processed": 510,
            "records_expected": 510,
            "data_health_score": 96,
            "compliance_score": 99,
        },
        "null_rate_by_column": [
            {"column": "patient_id",    "null_pct": 0.0, "threshold": 5.0},
            {"column": "age",           "null_pct": 0.0, "threshold": 5.0},
            {"column": "medication",    "null_pct": 0.0, "threshold": 5.0},
            {"column": "blood_pressure","null_pct": 0.6, "threshold": 5.0},
            {"column": "glucose_level", "null_pct": 0.4, "threshold": 5.0},
            {"column": "side_effect",   "null_pct": 1.2, "threshold": 5.0},
            {"column": "severity",      "null_pct": 0.0, "threshold": 5.0},
            {"column": "visit_date",    "null_pct": 0.0, "threshold": 5.0},
            {"column": "hospital_name", "null_pct": 0.0, "threshold": 5.0},
        ],
        "severity_distribution": [
            {"severity": "Critical", "count": 0, "pct": 0.0,  "color": "#EF4444"},
            {"severity": "High",     "count": 1, "pct": 20.0, "color": "#F59E0B"},
            {"severity": "Medium",   "count": 3, "pct": 60.0, "color": "#3B82F6"},
            {"severity": "Low",      "count": 1, "pct": 20.0, "color": "#10B981"},
        ],
        "records_vs_expected": {
            "actual": 510,
            "expected": 510,
            "gap": 0,
            "gap_pct": 0.0,
        },
        "agent_confidence": [
            {"agent": "Data Quality Agent",    "confidence": 96, "inferences": 31, "status": "Completed"},
            {"agent": "Log Analysis Agent",    "confidence": 94, "inferences": 19, "status": "Completed"},
            {"agent": "Root Cause Agent",      "confidence": 91, "inferences": 12, "status": "Completed"},
            {"agent": "Recommendation Agent", "confidence": 95, "inferences": 10, "status": "Completed"},
            {"agent": "Compliance Agent",      "confidence": 97, "inferences": 8,  "status": "Completed"},
        ],
        "anomaly_summary": [
            {"severity": "High",   "count": 1, "description": "Age outlier detected (>95 years)"},
            {"severity": "Medium", "count": 3, "description": "Minor glucose variance from mean"},
            {"severity": "Low",    "count": 1, "description": "Non-critical visit time offset"},
        ],
        "token_usage": {
            "run_total_input":  19800,
            "run_total_output": 6600,
            "run_total":        26400,
            "estimated_cost":   0.0224,
            "model":            "claude-sonnet-4",
            "by_agent": [
                {"agent": "Data Quality Agent",    "tokens": 10100, "pct": 38.3},
                {"agent": "Log Analysis Agent",    "tokens": 5400,  "pct": 20.5},
                {"agent": "Root Cause Agent",      "tokens": 4400,  "pct": 16.7},
                {"agent": "Recommendation Agent", "tokens": 3600,  "pct": 13.6},
                {"agent": "Compliance Agent",      "tokens": 2900,  "pct": 11.0},
            ],
        },
        "observability_pillars": [
            {"key": "freshness",    "label": "Freshness",    "icon": "clock",      "score": 99, "status": "normal", "detail": "Last visit: 2026-05-24", "color": "#10B981"},
            {"key": "schema",       "label": "Schema",       "icon": "layout",     "score": 100,"status": "normal", "detail": "10/10 validated · All columns present", "color": "#10B981"},
            {"key": "volume",       "label": "Volume",       "icon": "database",   "score": 100,"status": "normal", "detail": "Δ 0.0% from expected", "color": "#10B981"},
            {"key": "distribution", "label": "Distribution", "icon": "bar-chart",  "score": 89, "status": "normal", "detail": "2 clinical alert(s)", "color": "#10B981"},
            {"key": "lineage",      "label": "Lineage",      "icon": "git-branch", "score": 98, "status": "normal", "detail": "0 warnings", "color": "#10B981"},
        ],
        "agent_findings": {
            "data_quality": [
                {
                    "finding_type": "Age Outlier",
                    "severity": "high",
                    "confidence": 96,
                    "description": "1 patient record has age=97 which is outside the expected trial enrollment range of 18–80.",
                    "affected_field": "age",
                    "recommendation": "Verify patient eligibility. Check protocol inclusion/exclusion criteria for age.",
                },
            ],
            "log_analysis": [
                {
                    "finding_type": "Normal Pipeline Execution",
                    "severity": "low",
                    "confidence": 94,
                    "description": "All stages completed normally. Excellent run — fastest processing time this week.",
                    "affected_field": None,
                    "recommendation": "No action required. Baseline performance target met.",
                },
            ],
            "rca": [
                {
                    "finding_type": "Age Outlier — Likely Enrollment Error",
                    "severity": "high",
                    "confidence": 91,
                    "description": "Age=97 is likely a data entry error (97 entered instead of 57). No other patients over 80 in trial.",
                    "affected_field": "age",
                    "recommendation": "Contact data entry team to verify original source documents.",
                },
            ],
            "recommendation": [
                {
                    "finding_type": "Add Age Range Validation",
                    "severity": "medium",
                    "confidence": 95,
                    "description": "Implement protocol-specific range validation for age field at ingestion.",
                    "affected_field": "age",
                    "recommendation": "Validate age within 18–80 range per protocol inclusion criteria. Reject or flag on violation.",
                },
            ],
            "compliance": [
                {
                    "finding_type": "No Critical Compliance Issues",
                    "severity": "low",
                    "confidence": 97,
                    "description": "All compliance checks passed. Data meets ICH E6 GCP and 21 CFR Part 11 requirements.",
                    "affected_field": None,
                    "recommendation": "No action required.",
                },
            ],
        },
    },
}


# ─── Aggregate dummy data ─────────────────────────────────────────────────────

AGGREGATE_DATA: Dict[str, Any] = {
    "summary": {
        "total_runs": 3,
        "total_approved": 3,
        "total_anomalies": 31,
        "total_critical": 4,
        "avg_confidence_score": 86.3,
        "total_token_cost": 0.0746,
        "avg_records_per_run": 499,
    },
    "pipeline_runs_over_time": [
        {"date": "2026-05-20", "completed": 0, "failed": 0},
        {"date": "2026-05-21", "completed": 0, "failed": 0},
        {"date": "2026-05-22", "completed": 0, "failed": 0},
        {"date": "2026-05-23", "completed": 0, "failed": 0},
        {"date": "2026-05-24", "completed": 1, "failed": 0},
        {"date": "2026-05-25", "completed": 1, "failed": 0},
        {"date": "2026-05-26", "completed": 1, "failed": 0},
    ],
    "anomalies_trend": [
        {"date": "2026-05-20", "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"date": "2026-05-21", "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"date": "2026-05-22", "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"date": "2026-05-23", "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"date": "2026-05-24", "critical": 0, "high": 1, "medium": 3, "low": 1},
        {"date": "2026-05-25", "critical": 1, "high": 2, "medium": 4, "low": 2},
        {"date": "2026-05-26", "critical": 3, "high": 5, "medium": 7, "low": 2},
    ],
    "severity_distribution_aggregate": [
        {"severity": "Critical", "count": 4,  "pct": 12.9, "color": "#EF4444"},
        {"severity": "High",     "count": 8,  "pct": 25.8, "color": "#F59E0B"},
        {"severity": "Medium",   "count": 14, "pct": 45.2, "color": "#3B82F6"},
        {"severity": "Low",      "count": 5,  "pct": 16.1, "color": "#10B981"},
    ],
    "agent_performance_aggregate": [
        {"agent": "Data Quality Agent",    "avg_confidence": 92.0, "total_inferences": 93},
        {"agent": "Log Analysis Agent",    "avg_confidence": 84.3, "total_inferences": 57},
        {"agent": "Root Cause Agent",      "avg_confidence": 86.7, "total_inferences": 44},
        {"agent": "Recommendation Agent", "avg_confidence": 93.0, "total_inferences": 36},
        {"agent": "Compliance Agent",      "avg_confidence": 84.7, "total_inferences": 29},
    ],
    "token_usage_by_run": [
        {"run_id": "RUN-2026-0524-002", "total_tokens": 26400, "cost": 0.0224},
        {"run_id": "RUN-2026-0525-003", "total_tokens": 28400, "cost": 0.0241},
        {"run_id": "RUN-2026-0526-001", "total_tokens": 33150, "cost": 0.0281},
    ],
    "run_status_distribution": [
        {"name": "Approved", "value": 3, "color": "#10B981"},
        {"name": "Failed",   "value": 0, "color": "#EF4444"},
        {"name": "Pending",  "value": 0, "color": "#F59E0B"},
    ],
    "top_anomaly_types": [
        {"type": "Null Rate Violation",       "count": 8},
        {"type": "Out-of-Range Value",        "count": 7},
        {"type": "Distribution Drift",        "count": 6},
        {"type": "Protocol Deviation",        "count": 5},
        {"type": "Compliance Violation",      "count": 5},
    ],
    "pillar_scores_aggregate": [
        {"key": "freshness",    "label": "Freshness",    "avg_score": 88.3, "worst_run": "RUN-2026-0526-001"},
        {"key": "schema",       "label": "Schema",       "avg_score": 100,  "worst_run": None},
        {"key": "volume",       "label": "Volume",       "avg_score": 97.3, "worst_run": "RUN-2026-0525-003"},
        {"key": "distribution", "label": "Distribution", "avg_score": 76.0, "worst_run": "RUN-2026-0526-001"},
        {"key": "lineage",      "label": "Lineage",      "avg_score": 91.0, "worst_run": "RUN-2026-0526-001"},
    ],
}


# ─── Public service functions ─────────────────────────────────────────────────

def get_approved_runs() -> List[Dict]:
    return APPROVED_RUNS


def get_segregated_kpis(run_id: str) -> Dict:
    run = RUN_DATA.get(run_id)
    if not run:
        return {}
    return run["kpis"]


def get_null_rate(run_id: str) -> List[Dict]:
    return RUN_DATA.get(run_id, {}).get("null_rate_by_column", [])


def get_severity_distribution(run_id: str) -> List[Dict]:
    return RUN_DATA.get(run_id, {}).get("severity_distribution", [])


def get_records_vs_expected(run_id: str) -> Dict:
    return RUN_DATA.get(run_id, {}).get("records_vs_expected", {})


def get_agent_confidence(run_id: str) -> List[Dict]:
    return RUN_DATA.get(run_id, {}).get("agent_confidence", [])


def get_anomaly_summary(run_id: str) -> List[Dict]:
    return RUN_DATA.get(run_id, {}).get("anomaly_summary", [])


def get_token_usage(run_id: str) -> Dict:
    return RUN_DATA.get(run_id, {}).get("token_usage", {})


def get_pillars(run_id: str) -> List[Dict]:
    return RUN_DATA.get(run_id, {}).get("observability_pillars", [])


def get_agent_findings(run_id: str, agent: str) -> List[Dict]:
    findings = RUN_DATA.get(run_id, {}).get("agent_findings", {})
    return findings.get(agent, [])


def get_run_info(run_id: str) -> Dict:
    for r in APPROVED_RUNS:
        if r["run_id"] == run_id:
            return r
    return {}


def get_aggregate_summary() -> Dict:
    return AGGREGATE_DATA["summary"]


def get_aggregate_pipeline_runs_over_time() -> List[Dict]:
    return AGGREGATE_DATA["pipeline_runs_over_time"]


def get_aggregate_anomalies_trend() -> List[Dict]:
    return AGGREGATE_DATA["anomalies_trend"]


def get_aggregate_severity_distribution() -> List[Dict]:
    return AGGREGATE_DATA["severity_distribution_aggregate"]


def get_aggregate_agent_performance() -> List[Dict]:
    return AGGREGATE_DATA["agent_performance_aggregate"]


def get_aggregate_token_usage_by_run() -> List[Dict]:
    return AGGREGATE_DATA["token_usage_by_run"]


def get_aggregate_run_status_distribution() -> List[Dict]:
    return AGGREGATE_DATA["run_status_distribution"]


def get_aggregate_top_anomaly_types() -> List[Dict]:
    return AGGREGATE_DATA["top_anomaly_types"]


def get_aggregate_pillar_scores() -> List[Dict]:
    return AGGREGATE_DATA["pillar_scores_aggregate"]
