"""
backend/models/schemas.py
─────────────────────────────────────────────────────
All Pydantic v2 request and response schemas.
The frontend calls these endpoints with exactly these field names.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    fullName: str
    username: str
    email: str
    password: str
    role: str


class ForgotPasswordRequest(BaseModel):
    email: str


class UserOut(BaseModel):
    id: str
    username: str
    fullName: str
    email: str
    role: str
    avatar_initials: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[UserOut] = None
    error: Optional[str] = None


class SignupResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[UserOut] = None
    error: Optional[str] = None


class LogoutResponse(BaseModel):
    success: bool
    message: str


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str


# ─── System ───────────────────────────────────────────────────────────────────

class ServiceStatuses(BaseModel):
    kafka: str
    agents: str
    api: str
    storage: str


class SystemStatusResponse(BaseModel):
    status: str
    services: ServiceStatuses
    version: str
    uptime_seconds: int


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineRunSummary(BaseModel):
    run_id: str
    input_mode: str
    rows: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    description: Optional[str] = None


class PipelineRunsResponse(BaseModel):
    runs: List[PipelineRunSummary]
    total: int
    page: int
    limit: int


class RecentRunsResponse(BaseModel):
    runs: List[PipelineRunSummary]
    total: int


class ActiveRunResponse(BaseModel):
    run_id: Optional[str]
    status: str
    review_status: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ColumnInfo(BaseModel):
    name: str
    type: str
    sample: Optional[str] = None
    null_count: int
    null_pct: float


class UploadResponse(BaseModel):
    run_id: str
    filename: str
    file_size_mb: float
    total_rows: int
    total_columns: int
    detected_format: str
    encoding: str
    columns: List[ColumnInfo]
    file_hash: str
    saved_to: str


class GenerateSyntheticRequest(BaseModel):
    scenario: str = "normal"
    rows: int = 500
    null_rate: float = 0.02
    outlier_pct: float = 0.05
    date_drift_days: int = 0
    duplicate_rate: float = 0.01


class SyntheticPreview(BaseModel):
    null_rate_avg: float
    outlier_pct: float
    severity_distribution: Dict[str, int]


class GenerateSyntheticResponse(BaseModel):
    run_id: str
    scenario: str
    rows_generated: int
    columns: List[str]
    saved_to: str
    generated_at: str
    preview: SyntheticPreview


class TestApiConnectionRequest(BaseModel):
    url: str
    auth_type: str = "None"
    token: Optional[str] = None
    poll_interval_seconds: int = 30
    max_records_per_poll: int = 500


class TestApiConnectionResponse(BaseModel):
    connected: bool
    endpoint: Optional[str] = None
    auth_type: Optional[str] = None
    response_format: Optional[str] = None
    avg_latency_ms: Optional[float] = None
    sample_record_count: Optional[int] = None
    field_names: Optional[List[str]] = None
    error: Optional[str] = None


class PreflightHardBlock(BaseModel):
    id: str
    check: str
    column: Optional[str] = None
    message: str
    detail: Optional[str] = None


class PreflightSoftWarning(BaseModel):
    id: str
    check: str
    column: Optional[str] = None
    message: str
    detail: Optional[str] = None


class CrossFieldViolation(BaseModel):
    rule: str
    affected_rows: int
    example: Optional[str] = None


class PreflightResponse(BaseModel):
    run_id: str
    passed: bool
    checked_at: str
    row_count: int
    hard_blocks: List[PreflightHardBlock]
    soft_warnings: List[PreflightSoftWarning]
    cross_field_violations: List[CrossFieldViolation]


class RunPipelineRequest(BaseModel):
    run_id: str
    run_name: Optional[str] = None
    input_mode: str = "csv"
    window_size: int = 5
    inter_event_delay_ms: int = 50
    description: Optional[str] = None
    api_url: Optional[str] = None
    api_auth_type: str = "None"
    api_token: Optional[str] = None
    api_max_records_per_poll: int = 500


class StageStatus(BaseModel):
    num: int
    label: str
    status: str   # pending | active | completed | failed
    duration_ms: Optional[int] = None


class RunPipelineResponse(BaseModel):
    run_id: str
    status: str
    started_at: str
    current_stage: str
    stage_index: int
    total_stages: int


class PipelineStatusResponse(BaseModel):
    run_id: str
    status: str
    current_stage: str
    stage_index: int
    total_stages: int
    stages: List[StageStatus]
    events_processed: int
    started_at: str


class ResetPipelineRequest(BaseModel):
    run_id: str


class ResetPipelineResponse(BaseModel):
    success: bool
    message: str


class KafkaHealthResponse(BaseModel):
    kafka_available: bool
    bootstrap_servers: str
    topic: str
    message: str


# ─── Streaming ────────────────────────────────────────────────────────────────

class ProducerStatus(BaseModel):
    status: str
    records_sent: int
    send_rate_msg_per_sec: float
    last_sent: Optional[str] = None
    errors: int


class ConsumerStatus(BaseModel):
    status: str
    records_consumed: int
    consumer_rate_msg_per_sec: float
    consumer_lag_avg: float
    last_consumed: Optional[str] = None
    errors: int


class TopicStatus(BaseModel):
    name: str
    status: str
    partitions: int
    replication_factor: int
    under_replicated: bool


class StreamingProgress(BaseModel):
    total_target_events: int
    events_processed: int
    events_pending: int
    pct_complete: float


class StreamingStatusResponse(BaseModel):
    run_id: str
    pipeline_status: str
    uptime_seconds: float
    events_processed: int
    events_per_sec_avg: float
    last_event_time: Optional[str] = None
    producer: ProducerStatus
    consumer: ConsumerStatus
    topic: TopicStatus
    progress: StreamingProgress


class LagDataPoint(BaseModel):
    timestamp: str
    consumer_lag: float


class LagHistoryResponse(BaseModel):
    run_id: str
    window: str
    lag_threshold: int
    data_points: List[LagDataPoint]


class ThroughputDataPoint(BaseModel):
    timestamp: str
    events_per_sec: float


class ThroughputHistoryResponse(BaseModel):
    run_id: str
    window: str
    avg_msg_per_sec: float
    data_points: List[ThroughputDataPoint]


class RecentEvent(BaseModel):
    event_id: str
    event_type: str
    time: str
    status: str


class RecentEventsResponse(BaseModel):
    events: List[RecentEvent]


class AgentStreamStatus(BaseModel):
    name: str
    status: str
    last_run: Optional[str] = None
    confidence: Optional[int] = None
    findings: Optional[str] = None


class AgentsStatusResponse(BaseModel):
    agents: List[AgentStreamStatus]


class LiveFinding(BaseModel):
    id: str
    severity: str
    message: str
    agent: str
    timestamp: str


class LiveFindingsResponse(BaseModel):
    findings: List[LiveFinding]


class WindowStatusResponse(BaseModel):
    current_window: int
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    events_in_window: int
    window_size: int
    rolling_metrics_status: str


# ─── Review / HITL ───────────────────────────────────────────────────────────

class PendingRunInfo(BaseModel):
    run_id: str
    input_mode: str
    filename: Optional[str] = None
    total_records: int
    window_size: int
    pipeline_status: str
    started_at: str
    completed_at: Optional[str] = None
    health_score: Optional[float] = None
    health_label: Optional[str] = None


class PendingRunsResponse(BaseModel):
    pending_runs: List[PendingRunInfo]


class KeyFinding(BaseModel):
    issue: str
    severity: str
    affected: int
    total: int
    percentage: float
    trend: str


class AgentFindings(BaseModel):
    name: str
    status: str
    confidence: int
    confidence_label: str
    flag_for_review: bool
    summary: str
    key_findings: List[KeyFinding]
    evidence: str
    recommendations: str
    insight: str


class ReviewSummary(BaseModel):
    total_agents: int
    completed: int
    high_confidence: int
    low_confidence: int
    critical_issues: int


class FindingsResponse(BaseModel):
    run_id: str
    agents: List[AgentFindings]
    overall_confidence: int
    attention_required: bool
    attention_message: Optional[str] = None
    review_summary: ReviewSummary


class AgentTokenUsage(BaseModel):
    name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class TokenUsageResponse(BaseModel):
    run_id: str
    agents: List[AgentTokenUsage]
    total_tokens: int
    total_cost_usd: float


class ArtifactInfo(BaseModel):
    name: str
    type: str
    size_kb: float
    path: str


class ArtifactsResponse(BaseModel):
    run_id: str
    artifacts: List[ArtifactInfo]


class ApproveRequest(BaseModel):
    run_id: str
    reviewer_id: str
    notes: Optional[str] = None
    escalate_to_compliance: bool = False


class ApproveResponse(BaseModel):
    success: bool
    run_id: str
    status: str
    approved_by: str
    approved_at: str
    dashboard_url: str


class RejectRequest(BaseModel):
    run_id: str
    reviewer_id: str
    reason: Optional[str] = None
    escalate_to_compliance: bool = False


class RejectResponse(BaseModel):
    success: bool
    run_id: str
    status: str
    rejected_by: str
    rejected_at: str


# ─── Dashboard ────────────────────────────────────────────────────────────────

class DashboardSummaryResponse(BaseModel):
    period: str
    total_runs: int
    total_runs_change_pct: float
    completed_runs: int
    completed_runs_change_pct: float
    anomalies_detected: int
    anomalies_change_pct: float
    critical_issues: int
    critical_issues_change_pct: float
    avg_confidence_score: float
    avg_confidence_change_pct: float


class PipelineRunTimePoint(BaseModel):
    time: str
    completed: int
    failed: int
    in_progress: int


class PipelineRunsOverTimeResponse(BaseModel):
    granularity: str
    data: List[PipelineRunTimePoint]


class SeverityBreakdown(BaseModel):
    severity: str
    count: int
    pct: float
    color: str


class AnomaliesBySeverityResponse(BaseModel):
    total: int
    breakdown: List[SeverityBreakdown]
    change_pct: float


class AgentPerformance(BaseModel):
    name: str
    status: str
    runs: int
    avg_confidence: float
    issues: int


class AgentsPerformanceResponse(BaseModel):
    agents: List[AgentPerformance]


class AgentTokenShare(BaseModel):
    name: str
    tokens: int
    pct: float


class TokenUsageDashboardResponse(BaseModel):
    total_tokens: int
    total_cost_usd: float
    runs: int
    cost_per_run: float
    by_agent: List[AgentTokenShare]
    by_run: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineHealthResponse(BaseModel):
    health_score: float
    health_label: str
    availability_pct: float
    success_rate_pct: float
    avg_processing_time_seconds: float
    events_processed: int


class AnomalyTrendPoint(BaseModel):
    date: str
    critical: int
    high: int
    medium: int
    low: int


class AnomalyTrendResponse(BaseModel):
    data: List[AnomalyTrendPoint]


class AnomalyType(BaseModel):
    type: str
    count: int
    pct: float


class TopAnomalyTypesResponse(BaseModel):
    anomaly_types: List[AnomalyType]


class StatusCount(BaseModel):
    count: int
    pct: float


class RunStatusDistributionResponse(BaseModel):
    total: int
    completed: StatusCount
    failed: StatusCount
    in_progress: StatusCount
    change_pct: float


class RecentAlertItem(BaseModel):
    id: str
    severity: str
    title: str
    agent: str
    time: str


class RecentAlertsDashboardResponse(BaseModel):
    alerts: List[RecentAlertItem]


class RunTokensResponse(BaseModel):
    per_agent: List[Dict[str, Any]]
    run_total_tokens: int
    run_total_cost_usd: float


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total_24h: int
    change_pct: float


class AlertItem(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    source: str
    run_id: Optional[str] = None
    time: str
    status: str


class AlertsListResponse(BaseModel):
    total: int
    page: int
    limit: int
    summary: AlertSummary
    alerts: List[AlertItem]


class AlertMetrics(BaseModel):
    null_rate_pct: Optional[float] = None
    threshold_pct: Optional[float] = None
    affected_records: Optional[int] = None
    total_records: Optional[int] = None
    column: Optional[str] = None


class AlertHistoryEntry(BaseModel):
    action: str
    by: str
    at: str


class AlertDetailResponse(BaseModel):
    id: str
    severity: str
    is_new: bool
    title: str
    source: str
    triggered_at: str
    run_id: Optional[str] = None
    description: str
    impact: str
    metrics: AlertMetrics
    recommended_action: str
    history: List[AlertHistoryEntry]


class AcknowledgeAlertRequest(BaseModel):
    acknowledged_by: str
    note: Optional[str] = None


class AcknowledgeAlertResponse(BaseModel):
    success: bool
    alert_id: str
    status: str
    acknowledged_by: str
    acknowledged_at: str


class EscalateAlertRequest(BaseModel):
    escalated_by: str
    reason: Optional[str] = None


class EscalateAlertResponse(BaseModel):
    success: bool
    alert_id: str
    status: str
    escalated_at: str


class ReadAlertRequest(BaseModel):
    alert_id: str


class ReadAlertResponse(BaseModel):
    success: bool
    alert_id: str
    read: bool


# ─── Audit Trail ─────────────────────────────────────────────────────────────

class AuditSummaryResponse(BaseModel):
    period: Dict[str, Optional[str]]
    total_events: int
    total_events_change_pct: float
    ai_agent_executions: int
    ai_executions_change_pct: float
    data_access_events: int
    data_access_change_pct: float
    user_actions: int
    user_actions_change_pct: float
    errors: int
    errors_change_pct: float


class AuditEventItem(BaseModel):
    id: str
    time: str
    event_type: str
    event_type_color: str
    agent_source: str
    description: str
    detail: str
    user: str
    status: str
    run_id: Optional[str] = None


class AuditEventsResponse(BaseModel):
    total: int
    page: int
    limit: int
    events: List[AuditEventItem]


class AgentInfo(BaseModel):
    name: str
    model: str
    version: str


class TokenUsageDetail(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class EventDetailInfo(BaseModel):
    description: str
    task: str
    status: str
    duration_seconds: float


class RequestResponseInfo(BaseModel):
    prompt_path: Optional[str] = None
    response_path: Optional[str] = None


class EventMetadata(BaseModel):
    source_ip: str
    environment: str
    platform: str
    session_id: str
    user: str


class AuditEventDetailResponse(BaseModel):
    id: str
    event_type: str
    status: str
    time: str
    run_id: Optional[str] = None
    agent: AgentInfo
    token_usage: TokenUsageDetail
    event_details: EventDetailInfo
    request_response: RequestResponseInfo
    metadata: EventMetadata


class AuditPromptResponse(BaseModel):
    event_id: str
    prompt: str
