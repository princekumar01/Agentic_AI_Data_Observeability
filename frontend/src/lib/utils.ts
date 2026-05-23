// lib/utils.ts
export function formatTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatDateTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms/1000).toFixed(1)}s`;
  return `${Math.floor(ms/60000)}m ${Math.floor((ms%60000)/1000)}s`;
}

export function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n/1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n/1000).toFixed(1)}K`;
  return String(n);
}

export function classNames(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function severityColor(severity: string): string {
  const s = severity?.toUpperCase();
  if (s === 'CRITICAL') return 'var(--accent-red)';
  if (s === 'HIGH') return 'var(--accent-orange)';
  if (s === 'MEDIUM') return 'var(--accent-blue)';
  if (s === 'LOW') return 'var(--accent-green)';
  return 'var(--text-muted)';
}

export function confidenceColor(score: number): string {
  if (score >= 80) return 'var(--accent-green)';
  if (score >= 60) return 'var(--accent-orange)';
  return 'var(--accent-red)';
}

export function agentLabel(name: string): string {
  const map: Record<string, string> = {
    data_quality_agent: 'Data Quality', data_quality: 'Data Quality',
    log_analysis_agent: 'Log Analysis', log_analysis: 'Log Analysis',
    rca_agent: 'Root Cause', rca: 'Root Cause',
    recommendation_agent: 'Recommendations', recommendation: 'Recommendations',
    compliance_agent: 'Compliance', compliance: 'Compliance',
  };
  return map[name] || name;
}

export function agentColor(name: string): string {
  const map: Record<string, string> = {
    data_quality_agent: '#06B6D4', data_quality: '#06B6D4',
    log_analysis_agent: '#3B82F6', log_analysis: '#3B82F6',
    rca_agent: '#EF4444', rca: '#EF4444',
    recommendation_agent: '#10B981', recommendation: '#10B981',
    compliance_agent: '#7C3AED', compliance: '#7C3AED',
  };
  return map[name] || '#8BACC8';
}

// lib/constants.ts
export const SCENARIOS = [
  { value: 'normal', label: 'Normal — baseline healthy dataset' },
  { value: 'high_nulls', label: 'High Nulls — 40% glucose_level missing' },
  { value: 'glucose_spike', label: 'Glucose Spike — IQR outlier surge' },
  { value: 'full_chaos', label: 'Full Chaos — all anomalies simultaneously' },
  { value: 'age_drift', label: 'Age Drift — cohort demographic shift' },
  { value: 'severity_imbalance', label: 'Severity Imbalance — 90% Critical' },
  { value: 'stale_data', label: 'Stale Data — all visits 30+ days old' },
  { value: 'duplicates', label: 'Duplicates — 20% duplicate patient_id' },
];

export const ROLES = [
  'Clinical Data Manager',
  'Principal Investigator',
  'Data Scientist',
  'Regulatory Affairs Specialist',
  'Clinical Research Associate',
  'System Administrator',
  'Biostatistician',
];

export const AGENT_NAMES = [
  'data_quality_agent',
  'log_analysis_agent',
  'rca_agent',
  'recommendation_agent',
  'compliance_agent',
];

export const PILLAR_ICONS: Record<string, string> = {
  Freshness: '⏱️',
  Volume: '📊',
  Schema: '🔷',
  Distribution: '📈',
  Lineage: '🔗',
};
