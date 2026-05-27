// lib/types.ts — Aligned with backend responses

export interface User {
  id: string;
  username: string;
  fullName: string;
  email: string;
  role: string;
  avatar_initials: string;
}

export interface AuthContextType {
  token: string | null;
  user: User | null;
  login: (token: string, user: User) => void;
  logout: () => void;
}

// ── Pipeline ──────────────────────────────────────────────────────────────────
export interface Run {
  run_id: string;
  input_mode: string;
  rows?: number;
  records_processed?: number;
  status: string;
  review_status?: string | null;
  started_at: string;
  completed_at?: string | null;
  description?: string;
  health_score?: number;
  health_label?: string;
}

export interface PipelineStage {
  num: number;
  label: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  duration_ms?: number | null;
}

export interface PipelineStatus {
  run_id: string;
  status: string;
  current_stage: string;
  stage_index: number;
  total_stages: number;
  stages: PipelineStage[];
  events_processed: number;
  started_at: string;
}

export interface ColumnInfo {
  name: string;
  type: string;
  sample: string;
  null_count: number;
  null_pct: number;
}

export interface UploadResult {
  run_id: string;
  filename: string;
  file_size_mb: number;
  total_rows: number;
  total_columns: number;
  detected_format: string;
  encoding: string;
  columns: ColumnInfo[];
  file_hash: string;
  saved_to: string;
}

// ── Streaming ─────────────────────────────────────────────────────────────────
export interface StreamingStatus {
  run_id: string;
  pipeline_status: string;
  uptime?: string;
  uptime_seconds?: number;
  records_processed?: number;
  events_processed?: number;
  throughput_per_sec?: number;
  events_per_sec_avg?: number;
  consumer_lag?: number;
  anomalies_detected?: number;
  partitions?: number;
  kafka_connected?: boolean;
  producer?: { status: string; records_sent: number; send_rate_msg_per_sec: number; errors: number };
  consumer?: { status: string; records_consumed: number; consumer_lag_avg: number; errors: number };
  topic?: { name: string; status: string; partitions: number };
}

export interface AgentStatus {
  agent_id: string;
  name: string;
  status: string;
  last_run: string;
  confidence: number;
  inferences: number;
  findings_count: number;
  avg_latency_ms: number;
}

export interface StreamingEvent {
  event_type: string;
  message: string;
  severity?: string | null;
  agent?: string | null;
  record_id?: string | null;
  timestamp: string;
}

export interface AIFinding {
  finding_type: string;
  severity: string;
  confidence: number;
  description: string;
  agent: string;
  record_ids: string[];
  affected_field?: string | null;
  recommendation?: string;
}

// ── Review ────────────────────────────────────────────────────────────────────
export interface ReviewFinding {
  finding_type: string;
  severity: string;
  confidence: number;
  description: string;
  agent: string;
  affected_field?: string | null;
  record_ids: string[];
  recommendation?: string;
}

export interface TokenUsage {
  run_id?: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  model?: string;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export interface PipelineHealth {
  overall?: string;
  [key: string]: any;
}

// ── Segregated Dashboard ──────────────────────────────────────────────────────
export interface ApprovedRun {
  run_id: string;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  records_processed: number;
  records_expected: number;
  status: string;
  model: string;
  approved_at: string;
  approved_by: string;
}

export interface RunKpis {
  anomalies_detected: number;
  critical_count: number;
  high_count: number;
  records_processed: number;
  records_expected: number;
  data_health_score: number;
  compliance_score: number;
}

export interface NullRateColumn {
  column: string;
  null_pct: number;
  threshold: number;
}

export interface SeverityItem {
  severity: string;
  count: number;
  pct: number;
  color: string;
}

export interface AgentConfidence {
  agent: string;
  confidence: number;
  inferences: number;
  status: string;
}

export interface AnomalySummaryItem {
  severity: string;
  count: number;
  description: string;
}

export interface SegregatedTokenUsage {
  run_total_input: number;
  run_total_output: number;
  run_total: number;
  estimated_cost: number;
  model: string;
  by_agent: { agent: string; tokens: number; pct: number }[];
}

export interface Pillar {
  key: string;
  label: string;
  icon: string;
  score: number;
  status: 'normal' | 'warning' | 'critical';
  detail: string;
  color: string;
}

export interface Finding {
  finding_type: string;
  severity: string;
  confidence: number;
  description: string;
  affected_field: string | null;
  recommendation: string;
}

// ── Alerts ────────────────────────────────────────────────────────────────────
export interface Alert {
  id: string;
  severity: string;
  title: string;
  message?: string;
  description?: string;
  source?: string;
  run_id?: string;
  triggered_at: string;
  acknowledged_at?: string;
  status: string;
  read?: boolean;
  category?: string;
  recommendation?: string;
}

// ── Audit ─────────────────────────────────────────────────────────────────────
export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  user?: string;
  run_id?: string;
  details?: string;
  ip_address?: string;
  has_prompt?: boolean;
  metadata?: Record<string, any>;
  hash?: string;
}

export interface SystemStatus {
  status: string;
  services?: { kafka: string; agents: string; api: string; storage: string };
  version?: string;
  uptime_seconds?: number;
}
