const BASE = ((import.meta as any).env?.VITE_API_URL) || 'http://localhost:8000';
const PIPELINE_API_KEY = ((import.meta as any).env?.VITE_PIPELINE_API_KEY as string | undefined) || '';

function getToken(): string | null {
  return sessionStorage.getItem('ct_token');
}

function getCurrentUser(): any | null {
  const raw = sessionStorage.getItem('ct_user');
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function apiFetch(path: string, opts: RequestInit = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (PIPELINE_API_KEY) headers['X-API-Key'] = PIPELINE_API_KEY;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const e: any = new Error(err.detail || res.statusText);
    e.status = res.status;
    e.detail = err.detail;
    throw e;
  }
  return res.json();
}

async function apiFetchBlob(path: string): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (PIPELINE_API_KEY) headers['X-API-Key'] = PIPELINE_API_KEY;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(res.statusText);
  return res.blob();
}

async function apiUpload(path: string, formData: FormData): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || res.statusText), { status: res.status });
  }
  return res.json();
}

// AUTH
export const authApi = {
  login: (username: string, password: string) =>
    apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  signup: (data: any) =>
    apiFetch('/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
  logout: () =>
    apiFetch('/auth/logout', { method: 'POST', body: '{}' }),
  forgotPassword: (email: string) =>
    apiFetch('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),
};

// SYSTEM
export const systemApi = {
  status: () => apiFetch('/system/status'),
};

// PIPELINE
export const pipelineApi = {
  getRuns: (page = 1, limit = 10) => apiFetch(`/pipeline/runs?page=${page}&limit=${limit}`),
  getRecentRuns: (limit = 5) => apiFetch(`/pipeline/runs/recent?limit=${limit}`),
  getActiveRun: () => apiFetch('/pipeline/runs/active'),
  uploadFile: (file: File, runId?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    if (runId) fd.append('run_id', runId);
    return apiUpload('/pipeline/upload', fd);
  },
  generateSynthetic: (data: any) =>
    apiFetch('/pipeline/generate-synthetic', { method: 'POST', body: JSON.stringify(data) }),
  testApiConnection: (data: any) =>
    apiFetch('/pipeline/test-api-connection', { method: 'POST', body: JSON.stringify(data) }),
  runPreflight: (runId: string) =>
    apiFetch(`/pipeline/preflight/${runId}`, { method: 'POST', body: JSON.stringify({ run_id: runId }) }),
  getPreflightReport: (runId: string) =>
    apiFetch(`/pipeline/preflight/${runId}`),
  runPipeline: (data: any) =>
    apiFetch('/pipeline/run', { method: 'POST', body: JSON.stringify(data) }),
  getStatus: (runId: string) => apiFetch(`/pipeline/status/${runId}`),
  reset: (runId: string) =>
    apiFetch('/pipeline/reset', { method: 'POST', body: JSON.stringify({ run_id: runId }) }),
  kafkaHealth: () => apiFetch('/pipeline/kafka-health'),
};

// STREAMING — all routes require a run_id
export const streamingApi = {
  getStatus: (runId: string) => apiFetch(`/streaming/status/${runId}`),
  getLagHistory: (runId: string) => apiFetch(`/streaming/lag-history/${runId}`),
  getThroughputHistory: (runId: string) => apiFetch(`/streaming/throughput-history/${runId}`),
  getRecentEvents: (runId: string, limit = 20) => apiFetch(`/streaming/events/recent/${runId}?limit=${limit}`),
  getAgentsStatus: (runId: string) => apiFetch(`/streaming/agents/status/${runId}`),
  getAIFindings: (runId: string, limit = 30) => apiFetch(`/streaming/ai-findings/live/${runId}?limit=${limit}`),
  getWindowStatus: (runId: string) => apiFetch(`/streaming/window/status/${runId}`),
};

// REVIEW
function normalizeReviewFindings(data: any) {
  const agents = Array.isArray(data?.agents) ? data.agents : [];
  return agents.flatMap((agent: any) => {
    const agentId = String(agent.name ?? '').replace(/_agent$/, '');
    const findings = Array.isArray(agent.key_findings) ? agent.key_findings : [];
    if (findings.length === 0 && (agent.summary || agent.evidence || agent.recommendations)) {
      return [{
        finding_type: agent.summary || agent.name,
        severity: agent.flag_for_review ? 'high' : 'info',
        confidence: agent.confidence ?? 0,
        description: agent.evidence || agent.summary || '',
        agent: agentId,
        affected_field: null,
        record_ids: [],
        recommendation: agent.recommendations || agent.insight || '',
      }];
    }
    return findings.map((finding: any) => ({
      finding_type: finding.issue ?? agent.summary ?? agent.name,
      severity: String(finding.severity ?? 'info').toLowerCase(),
      confidence: agent.confidence ?? 0,
      description: agent.evidence || agent.summary || finding.issue || '',
      agent: agentId,
      affected_field: finding.column ?? null,
      record_ids: [],
      recommendation: agent.recommendations || agent.insight || '',
    }));
  });
}

function normalizeReviewTokenUsage(data: any) {
  const agents = Array.isArray(data?.agents) ? data.agents : [];
  const input = agents.reduce((sum: number, item: any) => sum + Number(item.input_tokens ?? 0), 0);
  const output = agents.reduce((sum: number, item: any) => sum + Number(item.output_tokens ?? 0), 0);
  return {
    run_id: data?.run_id,
    input_tokens: input,
    output_tokens: output,
    total_tokens: Number(data?.total_tokens ?? input + output),
    estimated_cost: Number(data?.total_cost_usd ?? 0),
    model: agents.length ? `${agents.length} agents` : 'No token usage recorded',
    agents,
  };
}

function normalizeArtifacts(data: any) {
  return (Array.isArray(data?.artifacts) ? data.artifacts : []).map((item: any) => ({
    ...item,
    size: `${Number(item.size_kb ?? 0).toFixed(1)} KB`,
  }));
}

function withReviewer(data: any, key: 'reviewer_id' | 'acknowledged_by' | 'escalated_by') {
  const user = getCurrentUser();
  return {
    ...data,
    [key]: data?.[key] || user?.username || user?.id || 'unknown',
  };
}

export const reviewApi = {
  getPending: () => apiFetch('/review/pending').then(d =>
    (Array.isArray(d?.pending_runs) ? d.pending_runs : []).map((run: any) => ({
      ...run,
      records_processed: run.total_records ?? run.records_processed ?? 0,
    }))
  ),
  getFindings: (runId: string) => apiFetch(`/review/findings/${runId}`).then(normalizeReviewFindings),
  getTokenUsage: (runId: string) => apiFetch(`/review/token-usage/${runId}`).then(normalizeReviewTokenUsage),
  getArtifacts: (runId: string) => apiFetch(`/review/artifacts/${runId}`).then(normalizeArtifacts),
  approve: (data: any) =>
    apiFetch('/review/approve', { method: 'POST', body: JSON.stringify(withReviewer(data, 'reviewer_id')) }),
  reject: (data: any) =>
    apiFetch('/review/reject', { method: 'POST', body: JSON.stringify(withReviewer(data, 'reviewer_id')) }),
};

// DASHBOARD — matches backend route names exactly
function dashboardList(data: any, key: string) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.[key])) return data[key];
  return [];
}

export const dashboardApi = {
  getSummary: () => apiFetch('/dashboard/summary').then(d => ({
    ...d,
    total_anomalies: d?.anomalies_detected ?? 0,
    runs_trend: d?.total_runs_change_pct ?? 0,
    anomalies_trend: d?.anomalies_change_pct ?? 0,
    confidence_trend: d?.avg_confidence_change_pct ?? 0,
    cost_trend: 0,
  })),
  getPipelineRunsOverTime: () => apiFetch('/dashboard/pipeline-runs-over-time').then(d => dashboardList(d, 'data')),
  getAnomaliesBySeverity: () => apiFetch('/dashboard/anomalies-by-severity').then(d =>
    dashboardList(d, 'breakdown').map((item: any) => ({
      ...item,
      name: item.name ?? item.severity,
      value: item.value ?? item.count ?? 0,
    }))
  ),
  getAgentsPerformance: () => apiFetch('/dashboard/agents-performance').then(d =>
    dashboardList(d, 'agents').map((agent: any) => ({
      ...agent,
      confidence: agent.confidence ?? agent.avg_confidence ?? 0,
      inferences: agent.inferences ?? agent.runs ?? 0,
    }))
  ),
  getTokenUsage: () => apiFetch('/dashboard/token-usage').then(d =>
    dashboardList(d, 'by_run').map((item: any) => ({
      ...item,
      run: item.run_id ?? item.run ?? item.name,
      cost: item.total_cost_usd ?? item.cost ?? 0,
    }))
  ),
  getPipelineHealth: () => apiFetch('/dashboard/pipeline-health'),
  getAnomaliesTrend: () => apiFetch('/dashboard/anomaly-trend').then(d => dashboardList(d, 'data')),
  getTopAnomalyTypes: () => apiFetch('/dashboard/top-anomaly-types').then(d => dashboardList(d, 'anomaly_types')),
  getRunStatusDistribution: () => apiFetch('/dashboard/run-status-distribution').then(d => {
    if (Array.isArray(d)) return d;
    return [
      { name: 'Completed', value: d?.completed?.count ?? 0, color: '#10B981' },
      { name: 'Failed', value: d?.failed?.count ?? 0, color: '#EF4444' },
      { name: 'In Progress', value: d?.in_progress?.count ?? 0, color: '#3B82F6' },
    ];
  }),
  getRecentAlerts: () => apiFetch('/dashboard/recent-alerts').then(d =>
    dashboardList(d, 'alerts').map((alert: any) => ({
      ...alert,
      triggered_at: alert.triggered_at ?? alert.time,
      severity: String(alert.severity ?? '').toLowerCase(),
    }))
  ),
  getRunTokens: (runId: string) => apiFetch(`/dashboard/run-tokens/${runId}`),
};

function normalizeAlertsResponse(data: any) {
  const alerts = Array.isArray(data) ? data : Array.isArray(data?.alerts) ? data.alerts : [];
  return alerts.map((alert: any) => ({
    ...alert,
    message: alert.message ?? alert.description ?? '',
    triggered_at: alert.triggered_at ?? alert.time,
    status: String(alert.status ?? '').toLowerCase(),
    severity: String(alert.severity ?? '').toLowerCase(),
  }));
}

function normalizeAuditEventsResponse(data: any) {
  const events = Array.isArray(data) ? data : Array.isArray(data?.events) ? data.events : [];
  return events.map((event: any, index: number) => ({
    ...event,
    row_key: [
      event.id,
      event.timestamp ?? event.time,
      event.event_type,
      event.run_id,
      index,
    ].filter(Boolean).join(':'),
    timestamp: event.timestamp ?? event.time,
    details: event.details ?? event.detail ?? event.description,
  }));
}

function normalizeAuditSummary(data: any) {
  return {
    ...data,
    pipeline_events: data?.pipeline_events ?? data?.ai_agent_executions ?? 0,
    alert_events: data?.alert_events ?? data?.errors ?? 0,
    prompt_events: data?.prompt_events ?? data?.data_access_events ?? 0,
  };
}

// ALERTS
export const alertsApi = {
  getAlerts: (params: Record<string, string | undefined> = {}) => {
    const statusMap: Record<string, string> = {
      new: 'New',
      active: 'New',
      acknowledged: 'Acknowledged',
      escalated: 'Escalated',
      resolved: 'Resolved',
      'in progress': 'In Progress',
    };
    const normalized = {
      ...params,
      status: params.status ? (statusMap[params.status] ?? params.status) : undefined,
    };
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(normalized).filter(([, v]) => v !== undefined)) as Record<string, string>
    ).toString();
    return apiFetch(`/alerts${qs ? '?' + qs : ''}`).then(normalizeAlertsResponse);
  },
  getAlert: (alertId: string) => apiFetch(`/alerts/${alertId}`),
  acknowledge: (alertId: string, note = '') =>
    apiFetch(`/alerts/${alertId}/acknowledge`, {
      method: 'POST', body: JSON.stringify(withReviewer({ note }, 'acknowledged_by')),
    }),
  escalate: (alertId: string, reason = '') =>
    apiFetch(`/alerts/${alertId}/escalate`, {
      method: 'POST', body: JSON.stringify(withReviewer({ reason }, 'escalated_by')),
    }),
  markRead: (alertId: string) =>
    apiFetch('/alerts/read', {
      method: 'POST', body: JSON.stringify({ alert_id: alertId }),
    }),
};

// AUDIT
export const auditApi = {
  getSummary: () => apiFetch('/audit/summary').then(normalizeAuditSummary),
  getEvents: (params: Record<string, string | undefined> = {}) => {
    const normalizedParams = {
      ...params,
      from_dt: params.from_date,
      to_dt: params.to_date,
      from_date: undefined,
      to_date: undefined,
    };
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(normalizedParams).filter(([, v]) => v !== undefined)) as Record<string, string>
    ).toString();
    return apiFetch(`/audit/events${qs ? '?' + qs : ''}`).then(normalizeAuditEventsResponse);
  },
  getEventDetail: (eventId: string) => apiFetch(`/audit/events/${eventId}`),
  getPrompt: (eventId: string) => apiFetch(`/audit/events/${eventId}/prompt`).then(d => ({
    agent: d?.event_id ?? eventId,
    system_prompt: d?.prompt ?? '',
    user_prompt: '',
    response: '',
    model: '',
    tokens: 0,
    latency_ms: 0,
  })),
  export: (format: 'csv' | 'json') => apiFetchBlob(`/audit/export?format=${format}`),
};
