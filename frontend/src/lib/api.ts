const BASE = ((import.meta as any).env?.VITE_API_URL) || 'http://localhost:8000';

function getToken(): string | null {
  return sessionStorage.getItem('ct_token');
}

async function apiFetch(path: string, opts: RequestInit = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
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
export const reviewApi = {
  getPending: () => apiFetch('/review/pending'),
  getFindings: (runId: string) => apiFetch(`/review/findings/${runId}`),
  getTokenUsage: (runId: string) => apiFetch(`/review/token-usage/${runId}`),
  getArtifacts: (runId: string) => apiFetch(`/review/artifacts/${runId}`),
  approve: (data: any) =>
    apiFetch('/review/approve', { method: 'POST', body: JSON.stringify(data) }),
  reject: (data: any) =>
    apiFetch('/review/reject', { method: 'POST', body: JSON.stringify(data) }),
};

// DASHBOARD — matches backend route names exactly
export const dashboardApi = {
  getSummary: () => apiFetch('/dashboard/summary'),
  getPipelineRunsOverTime: () => apiFetch('/dashboard/pipeline-runs-over-time'),
  getAnomaliesBySeverity: () => apiFetch('/dashboard/anomalies-by-severity'),
  getAgentsPerformance: () => apiFetch('/dashboard/agents-performance'),
  getTokenUsage: () => apiFetch('/dashboard/token-usage'),
  getPipelineHealth: () => apiFetch('/dashboard/pipeline-health'),
  getAnomaliesTrend: () => apiFetch('/dashboard/anomalies-trend'),
  getTopAnomalyTypes: () => apiFetch('/dashboard/top-anomaly-types'),
  getRunStatusDistribution: () => apiFetch('/dashboard/run-status-distribution'),
  getRecentAlerts: () => apiFetch('/dashboard/recent-alerts'),
  getRunTokens: (runId: string) => apiFetch(`/dashboard/${runId}/tokens`),
};

// ALERTS
export const alertsApi = {
  getAlerts: (params: Record<string, string | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>
    ).toString();
    return apiFetch(`/alerts${qs ? '?' + qs : ''}`);
  },
  getAlert: (alertId: string) => apiFetch(`/alerts/${alertId}`),
  acknowledge: (alertId: string, note = '') =>
    apiFetch(`/alerts/${alertId}/acknowledge`, {
      method: 'POST', body: JSON.stringify({ note }),
    }),
  escalate: (alertId: string, reason = '') =>
    apiFetch(`/alerts/${alertId}/escalate`, {
      method: 'POST', body: JSON.stringify({ reason }),
    }),
  markRead: (alertId: string) =>
    apiFetch(`/alerts/${alertId}/read`, {
      method: 'POST', body: JSON.stringify({}),
    }),
};

// AUDIT
export const auditApi = {
  getSummary: () => apiFetch('/audit/summary'),
  getEvents: (params: Record<string, string | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>
    ).toString();
    return apiFetch(`/audit/events${qs ? '?' + qs : ''}`);
  },
  getEventDetail: (eventId: string) => apiFetch(`/audit/events/${eventId}`),
  getPrompt: (eventId: string) => apiFetch(`/audit/events/${eventId}/prompt`),
  export: (format: 'csv' | 'json') => apiFetchBlob(`/audit/export?format=${format}`),
};
