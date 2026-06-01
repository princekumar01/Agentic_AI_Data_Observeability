import { useState, useEffect, useCallback } from 'react';
import {
  BarChart2, Activity, AlertTriangle, CheckCircle, Cpu,
  DollarSign, Clock, ChevronRight, Database, GitBranch,
  Layout, Eye, Layers, RefreshCw,
} from 'lucide-react';
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { segDashboardApi as dashboardApi, reviewApi } from '../lib/api';
import AnalyticalDashboard from './Dashboard';
import {
  ApprovedRun, RunKpis, NullRateColumn, SeverityItem,
  AgentConfidence, AnomalySummaryItem, SegregatedTokenUsage, Pillar, ReviewFinding,
} from '../lib/types';
import { formatDateTime, confidenceColor, severityColor } from '../lib/utils';

function formatRunDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

// ─── Design tokens ─────────────────────────────────────────────────────────
const CHART_STYLE = {
  grid: { stroke: 'rgba(255,255,255,0.05)', strokeDasharray: '3 3' },
  axis: { fill: '#8BACC8', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
  tooltip: {
    background: '#0D1E35', border: '1px solid #1A3050',
    color: '#E8F4FF', fontSize: 12, borderRadius: 8, padding: '8px 12px',
  },
};

const AGENT_TABS = [
  { id: 'data_quality',  label: 'Data Quality' },
  { id: 'log_analysis',  label: 'Log Analysis' },
  { id: 'rca',           label: 'Root Cause' },
  { id: 'recommendation',label: 'Recommendations' },
  { id: 'compliance',    label: 'Compliance' },
];

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

// ─── Small reusable pieces ──────────────────────────────────────────────────
function GlassCard({ children, className = '', style = {} }: {
  children: React.ReactNode; className?: string; style?: React.CSSProperties;
}) {
  return (
    <div className={`glass-card ${className}`} style={style}>
      {children}
    </div>
  );
}

function SectionLabel({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
      {icon} {children}
    </p>
  );
}

function LoadingSpinner({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      className="animate-spin-slow" style={{ flexShrink: 0 }}>
      <circle cx="12" cy="12" r="10" stroke="var(--accent-blue)" strokeWidth="2" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--accent-blue)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function SevBadge({ severity }: { severity: string }) {
  const c = severityColor(severity);
  return (
    <span style={{
      fontSize: 10, padding: '1px 7px', borderRadius: 10, fontWeight: 700,
      background: `${c}18`, color: c, border: `1px solid ${c}30`,
      fontFamily: 'Space Grotesk',
    }}>{severity}</span>
  );
}

function ConfBadge({ score }: { score: number }) {
  const c = confidenceColor(score);
  return (
    <span style={{
      fontSize: 10, padding: '1px 7px', borderRadius: 10, fontWeight: 700,
      background: `${c}18`, color: c, border: `1px solid ${c}30`,
      fontFamily: 'Space Grotesk',
    }}>{score}%</span>
  );
}

// ─── KPI Card ───────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, icon, color }: {
  label: string; value: string | number; sub?: string;
  icon: React.ReactNode; color: string;
}) {
  return (
    <GlassCard style={{ padding: '16px 18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <p style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', fontFamily: 'Space Grotesk' }}>{label}</p>
        <span style={{ color }}>{icon}</span>
      </div>
      <p style={{ fontSize: 28, fontWeight: 700, color, fontFamily: 'Space Grotesk', lineHeight: 1 }}>{value}</p>
      {sub && <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 5 }}>{sub}</p>}
    </GlassCard>
  );
}

// ─── Pillar Card ────────────────────────────────────────────────────────────
const PILLAR_ICONS: Record<string, React.ReactNode> = {
  freshness:    <Clock size={18} />,
  schema:       <Layout size={18} />,
  volume:       <Database size={18} />,
  distribution: <BarChart2 size={18} />,
  lineage:      <GitBranch size={18} />,
};

function PillarCard({ pillar }: { pillar: Pillar }) {
  const icon = PILLAR_ICONS[pillar.key] || <Activity size={18} />;
  const statusLabel = pillar.status === 'normal' ? 'Normal' : pillar.status === 'warning' ? 'Warning' : 'Critical';
  const statusColor = pillar.status === 'normal' ? '#10B981' : pillar.status === 'warning' ? '#F59E0B' : '#EF4444';
  return (
    <GlassCard style={{ padding: 14, textAlign: 'center' }}>
      <div style={{ color: pillar.color, marginBottom: 8, display: 'flex', justifyContent: 'center' }}>{icon}</div>
      <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'Space Grotesk', marginBottom: 6 }}>{pillar.label}</p>
      <p style={{ fontSize: 24, fontWeight: 700, color: pillar.color, fontFamily: 'Space Grotesk', marginBottom: 4 }}>{pillar.score}</p>
      <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, lineHeight: 1.4 }}>{pillar.detail}</p>
      <span style={{
        fontSize: 9, padding: '2px 8px', borderRadius: 10, fontWeight: 700,
        background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}30`,
        fontFamily: 'Space Grotesk',
      }}>{statusLabel}</span>
    </GlassCard>
  );
}

// ─── Finding row ────────────────────────────────────────────────────────────
function FindingRow({ f, onClick }: { f: ReviewFinding; onClick: () => void }) {
  const c = severityColor(f.severity);
  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
      background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)',
      borderRadius: 8, cursor: 'pointer', transition: 'border-color 0.15s',
    }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(59,130,246,0.4)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-color)')}
    >
      <div style={{ width: 7, height: 7, borderRadius: '50%', background: c, flexShrink: 0, marginTop: 5 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 3 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{f.finding_type}</span>
          <SevBadge severity={f.severity} />
          <ConfBadge score={f.confidence} />
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.45 }}>{f.description}</p>
        {f.affected_field && (
          <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
            Field: <code style={{ fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)' }}>{f.affected_field}</code>
          </p>
        )}
      </div>
      <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }} />
    </div>
  );
}

// ─── Finding Detail Modal ───────────────────────────────────────────────────
function FindingModal({ finding, onClose }: { finding: ReviewFinding | null; onClose: () => void }) {
  if (!finding) return null;
  const c = severityColor(finding.severity);
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(6,13,26,0.88)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div className="glass-card animate-fade-up" style={{ width: 580, maxWidth: '95vw', maxHeight: '85vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--border-color)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>Finding Detail</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <SevBadge severity={finding.severity} />
            <ConfBadge score={finding.confidence} />
          </div>
          <div>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Finding Type</p>
            <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{finding.finding_type}</p>
          </div>
          <div>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Description</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{finding.description}</p>
          </div>
          {finding.recommendation && (
            <div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Recommendation</p>
              <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 8, padding: '10px 14px' }}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{finding.recommendation}</p>
              </div>
            </div>
          )}
          {finding.affected_field && (
            <div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Affected Field</p>
              <code style={{ fontFamily: 'JetBrains Mono', fontSize: 13, color: '#93C5FD', background: 'rgba(59,130,246,0.1)', padding: '3px 8px', borderRadius: 6 }}>{finding.affected_field}</code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── SEGREGATED DASHBOARD ───────────────────────────────────────────────────
function SegregatedDashboard({ runId }: { runId: string }) {
  const [kpis, setKpis] = useState<RunKpis | null>(null);
  const [runInfo, setRunInfo] = useState<ApprovedRun | null>(null);
  const [nullRate, setNullRate] = useState<NullRateColumn[]>([]);
  const [severityDist, setSeverityDist] = useState<SeverityItem[]>([]);
  const [agentConf, setAgentConf] = useState<AgentConfidence[]>([]);
  const [anomalySummary, setAnomalySummary] = useState<AnomalySummaryItem[]>([]);
  const [tokenUsage, setTokenUsage] = useState<SegregatedTokenUsage | null>(null);
  const [activeAgent, setActiveAgent] = useState('data_quality');
  const [allFindings, setAllFindings] = useState<ReviewFinding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<ReviewFinding | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      dashboardApi.getRunInfo(runId),
      dashboardApi.getRunKpis(runId),
      dashboardApi.getNullRate(runId),
      dashboardApi.getSeverityDistribution(runId),
      dashboardApi.getAgentConfidence(runId),
      dashboardApi.getAnomalySummary(runId),
      dashboardApi.getTokenUsage(runId),
      reviewApi.getFindings(runId),
    ]).then(([ri, k, nr, sd, ac, as_, tu, findings]) => {
      setRunInfo(ri);
      setKpis(k);
      setNullRate(nr);
      setSeverityDist(sd);
      setAgentConf(ac);
      setAnomalySummary(as_);
      setTokenUsage(tu);
      setAllFindings(findings);
    }).catch(console.error).finally(() => setLoading(false));
  }, [runId]);

  const agentFindings = allFindings.filter(f => f.agent === activeAgent);
  const sortedFindings = [...agentFindings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  const agentSummary = (agentId: string) => {
    const aFindings = allFindings.filter(f => f.agent === agentId);
    const critical = aFindings.filter(f => f.severity === 'critical').length;
    const high = aFindings.filter(f => f.severity === 'high').length;
    const avgConf = aFindings.length
      ? Math.round(aFindings.reduce((s, f) => s + f.confidence, 0) / aFindings.length)
      : 0;
    return { count: aFindings.length, critical, high, avgConf };
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80 }}>
      <LoadingSpinner size={36} />
    </div>
  );

  // chart data transforms
  const pieData = severityDist.filter(s => s.count > 0).map(s => ({
    name: s.severity, value: s.count, color: s.color,
  }));

  const SEV_COLORS: Record<string, string> = {
    Critical: '#EF4444', High: '#F59E0B', Medium: '#3B82F6', Low: '#10B981',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} className="animate-fade-up">
      {/* Finding modal */}
      <FindingModal finding={selectedFinding} onClose={() => setSelectedFinding(null)} />

      {/* Pipeline Run Banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
        background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 10,
      }}>
        <div style={{ width: 36, height: 36, background: 'rgba(59,130,246,0.15)', borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Activity size={16} style={{ color: 'var(--accent-blue)' }} />
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 1 }}>Pipeline Run ID</p>
          <p style={{ fontFamily: 'JetBrains Mono', fontSize: 14, color: '#93C5FD', fontWeight: 500 }}>{runId}</p>
        </div>
        {runInfo && (
          <div style={{ display: 'flex', gap: 20, fontSize: 12, color: 'var(--text-secondary)' }}>
            <span><span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Started</span><b>{formatDateTime(runInfo.started_at)}</b></span>
            <span><span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Duration</span><b>{formatRunDuration(runInfo.duration_seconds)}</b></span>
            <span><span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Records</span><b>{runInfo.records_processed.toLocaleString()}</b></span>
          </div>
        )}
        <span style={{
          display: 'flex', alignItems: 'center', gap: 5, padding: '4px 12px',
          background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: 20, fontSize: 12, color: '#10B981', fontWeight: 700, fontFamily: 'Space Grotesk', flexShrink: 0,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
          Approved
        </span>
      </div>

      {/* KPI Cards */}
      {kpis && (
        <>
          <SectionLabel icon={<BarChart2 size={13} style={{ color: 'var(--accent-blue)' }} />}>Run Summary</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            <KpiCard
              label="Anomalies Detected"
              value={kpis.anomalies_detected}
              icon={<AlertTriangle size={18} />}
              color="#EF4444"
            />
            <KpiCard
              label="Records Processed"
              value={kpis.records_processed.toLocaleString()}
              icon={<Database size={18} />}
              color="#3B82F6"
            />
            <KpiCard
              label="Compliance Score"
              value={`${kpis.compliance_score}%`}
              icon={<CheckCircle size={18} />}
              color={kpis.compliance_score >= 95 ? '#10B981' : kpis.compliance_score >= 80 ? '#F59E0B' : '#EF4444'}
            />
          </div>
        </>
      )}

      {/* Row 1: Severity Distribution + Null Rate */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 10 }}>
        <GlassCard style={{ padding: 16 }}>
          <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <AlertTriangle size={13} style={{ color: '#EF4444' }} /> Severity Distribution
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ResponsiveContainer width={120} height={120}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" nameKey="name">
                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={CHART_STYLE.tooltip} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
              {severityDist.map((s, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.color, flexShrink: 0 }} />
                  <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{s.severity}</span>
                  <b style={{ color: 'var(--text-primary)', fontFamily: 'JetBrains Mono' }}>{s.count}</b>
                  <span style={{ color: 'var(--text-muted)', width: 38, textAlign: 'right' }}>{s.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>

        <GlassCard style={{ padding: 16 }}>
          <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
            <AlertTriangle size={13} style={{ color: 'var(--accent-orange)' }} /> Null Rate by Column
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={nullRate} barCategoryGap="20%">
              <CartesianGrid {...CHART_STYLE.grid} />
              <XAxis dataKey="column" tick={{ ...CHART_STYLE.axis, fontSize: 9 }} interval={0} angle={-25} textAnchor="end" />
              <YAxis tick={CHART_STYLE.axis} tickFormatter={v => `${v}%`} domain={[0, 10]} />
              <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: any) => [`${v}%`, 'Null Rate']} />
              <ReferenceLine y={5} stroke="#F59E0B" strokeDasharray="4 4"
                label={{ value: 'Threshold 5%', fill: '#F59E0B', fontSize: 9, position: 'insideTopRight' }} />
              <Bar dataKey="null_pct" name="Null %" radius={[3, 3, 0, 0]}>
                {nullRate.map((entry, i) => (
                  <Cell key={i} fill={entry.null_pct > entry.threshold ? '#EF4444' : entry.null_pct > entry.threshold * 0.6 ? '#F59E0B' : '#10B981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      {/* Row 2: Agent Confidence + Anomaly Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 10 }}>
        <GlassCard style={{ padding: 16 }}>
          <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
            <Cpu size={13} style={{ color: 'var(--accent-blue)' }} /> Agent Confidence
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {agentConf.map((a, i) => {
              const c = confidenceColor(a.confidence);
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 86, fontSize: 11, color: 'var(--text-secondary)', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.agent.replace(' Agent', '')}</div>
                  <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.07)', borderRadius: 10, overflow: 'hidden' }}>
                    <div style={{ height: '100%', borderRadius: 10, background: c, width: `${a.confidence}%`, transition: 'width 0.7s ease' }} />
                  </div>
                  <div style={{ width: 32, textAlign: 'right', fontSize: 11, fontFamily: 'JetBrains Mono', color: c, fontWeight: 600 }}>{a.confidence}%</div>
                </div>
              );
            })}
          </div>
        </GlassCard>

        <GlassCard style={{ padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={13} style={{ color: 'var(--accent-orange)' }} /> Anomaly Summary
            </p>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', fontStyle: 'italic' }}>for this run</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {anomalySummary.map((a, i) => {
              const c = SEV_COLORS[a.severity] || '#8BACC8';
              return (
                <div key={i} style={{ padding: '6px 10px', background: 'rgba(255,255,255,0.04)', borderLeft: '2px solid var(--border-color)', borderRadius: '0 6px 6px 0' }}>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{a.description}</p>
                </div>
              );
            })}
          </div>
        </GlassCard>
      </div>

      {/* Token Usage */}
      {tokenUsage && (
        <>
          <SectionLabel icon={<DollarSign size={13} style={{ color: '#7C3AED' }} />}>Token Usage · This Run</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 10 }}>
            <GlassCard style={{ padding: 16 }}>
              <p className="section-label" style={{ marginBottom: 12 }}>Run Total</p>
              {[
                { label: 'Input Tokens',  val: tokenUsage.run_total_input.toLocaleString(),  c: 'var(--text-primary)' },
                { label: 'Output Tokens', val: tokenUsage.run_total_output.toLocaleString(), c: 'var(--text-primary)' },
                { label: 'Total Tokens',  val: tokenUsage.run_total.toLocaleString(),         c: 'var(--accent-blue)' },
                { label: 'Est. Cost',     val: `$${tokenUsage.estimated_cost.toFixed(4)}`,   c: '#10B981' },
                { label: 'Model',         val: tokenUsage.model,                             c: 'var(--text-muted)' },
              ].map(({ label, val, c }, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: i < 4 ? '1px solid rgba(26,48,80,0.5)' : 'none' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
                  <span style={{ fontSize: 12, fontFamily: 'JetBrains Mono', color: c, fontWeight: 600 }}>{val}</span>
                </div>
              ))}
            </GlassCard>

            <GlassCard style={{ padding: 16 }}>
              <p className="section-label" style={{ marginBottom: 12 }}>Tokens by Agent</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {tokenUsage.by_agent.map((a, i) => {
                  const colors = ['#3B82F6', '#06B6D4', '#F97316', '#10B981', '#EF4444'];
                  const col = colors[i % colors.length];
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 106, fontSize: 11, color: 'var(--text-secondary)', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.agent.replace(' Agent', '')}</div>
                      <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.07)', borderRadius: 10, overflow: 'hidden' }}>
                        <div style={{ height: '100%', borderRadius: 10, background: col, width: `${a.pct}%`, transition: 'width 0.7s ease' }} />
                      </div>
                      <div style={{ width: 60, textAlign: 'right', fontSize: 10, fontFamily: 'JetBrains Mono', color: 'var(--text-muted)' }}>{a.tokens.toLocaleString()}</div>
                    </div>
                  );
                })}
              </div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'right', marginTop: 8 }}>from token_tracking_service · token_usage.json</p>
            </GlassCard>
          </div>
        </>
      )}



      {/* Agent Analysis — single /review/findings call, HITL-style tabs */}
      <SectionLabel icon={<Eye size={13} style={{ color: 'var(--accent-blue)' }} />}>Agent Analysis · Run Findings</SectionLabel>

      <GlassCard style={{ padding: 14, marginBottom: 10 }}>
        <p className="section-label" style={{ marginBottom: 10 }}>Agent Findings Summary</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 8 }}>
          {AGENT_TABS.map(tab => {
            const s = agentSummary(tab.id);
            const active = activeAgent === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveAgent(tab.id)}
                style={{
                  padding: '10px 12px', borderRadius: 8, textAlign: 'left', cursor: 'pointer',
                  background: active ? 'rgba(59,130,246,0.12)' : 'rgba(0,0,0,0.2)',
                  border: `1px solid ${active ? 'rgba(59,130,246,0.45)' : 'var(--border-color)'}`,
                }}
              >
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tab.label}</p>
                <p style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{s.count}</p>
                <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                  {s.critical > 0 && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: 'rgba(239,68,68,0.15)', color: '#F87171' }}>{s.critical}C</span>}
                  {s.high > 0 && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: 'rgba(245,158,11,0.15)', color: '#FBBF24' }}>{s.high}H</span>}
                </div>
                <p style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 4 }}>Avg conf: {s.avgConf}%</p>
              </button>
            );
          })}
        </div>
      </GlassCard>

      <GlassCard>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', overflowX: 'auto' }}>
          {AGENT_TABS.map(tab => {
            const s = agentSummary(tab.id);
            return (
              <button key={tab.id} onClick={() => setActiveAgent(tab.id)} style={{
                padding: '10px 16px', fontSize: 12, fontWeight: 600, fontFamily: 'Space Grotesk',
                borderBottom: `2px solid ${activeAgent === tab.id ? 'var(--accent-blue)' : 'transparent'}`,
                color: activeAgent === tab.id ? 'var(--accent-blue)' : 'var(--text-muted)',
                background: 'none', border: 'none',
                cursor: 'pointer', whiteSpace: 'nowrap', transition: 'color 0.15s',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                {tab.label}
                <span style={{
                  fontSize: 10, padding: '1px 6px', borderRadius: 10,
                  background: activeAgent === tab.id ? 'rgba(59,130,246,0.2)' : 'rgba(255,255,255,0.06)',
                  color: activeAgent === tab.id ? 'var(--accent-blue)' : 'var(--text-muted)',
                }}>{s.count}</span>
              </button>
            );
          })}
        </div>
        <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8, minHeight: 120 }}>
          {sortedFindings.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>
              <CheckCircle size={28} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
              <p style={{ fontSize: 13 }}>No findings for this agent</p>
            </div>
          ) : (
            sortedFindings.map((f, i) => (
              <FindingRow key={i} f={f} onClick={() => setSelectedFinding(f)} />
            ))
          )}
        </div>
      </GlassCard>
    </div>
  );
}





// ─── MAIN DASHBOARD ─────────────────────────────────────────────────────────
export default function Dashboard() {
  const [tab, setTab] = useState<'segregated' | 'aggregated'>('segregated');
  const [selectedRun, setSelectedRun] = useState<string>('');
  const [runsLoading, setRunsLoading] = useState(true);

  useEffect(() => {
    dashboardApi.getApprovedRuns()
      .then((data: ApprovedRun[]) => {
        if (data.length > 0) setSelectedRun(data[0].run_id);
      })
      .catch(console.error)
      .finally(() => setRunsLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', background: 'var(--bg-primary)' }}>
      {/* Topbar */}
      <header style={{
        height: 52, background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)',
        display: 'flex', alignItems: 'center', padding: '0 20px', gap: 14, flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 30, height: 30, background: 'var(--accent-blue)', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>🏥</div>
          <div>
            <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-blue)', fontFamily: 'Space Grotesk', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Clinical Trials</p>
            <p style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'Space Grotesk' }}>AI Observability</p>
          </div>
        </div>
        <div style={{ width: 1, height: 24, background: 'var(--border-color)' }} />
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'Space Grotesk' }}>
          Dashboard <span style={{ color: 'var(--text-muted)' }}>›</span>{' '}
          <span style={{ color: 'var(--text-primary)' }}>{tab === 'segregated' ? 'Segregated View' : 'Aggregated View'}</span>
        </p>
        <div style={{ flex: 1 }} />
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {new Date().toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
      </header>

      {/* Tab bar */}
      <div style={{
        background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)',
        padding: '0 20px', display: 'flex', alignItems: 'center', gap: 4,
      }}>
        {(['segregated', 'aggregated'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '11px 18px', fontSize: 12, fontWeight: 600, fontFamily: 'Space Grotesk',
            color: tab === t ? 'var(--accent-blue)' : 'var(--text-muted)',
            background: 'none', border: 'none',
            borderBottom: `2px solid ${tab === t ? 'var(--accent-blue)' : 'transparent'}`,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7, transition: 'color 0.15s',
          }}>
            {t === 'segregated' ? <Activity size={13} /> : <BarChart2 size={13} />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
            <span style={{
              fontSize: 9, padding: '1px 6px', borderRadius: 10, fontWeight: 700,
              background: tab === t ? 'rgba(59,130,246,0.2)' : 'rgba(74,111,165,0.15)',
              color: tab === t ? '#93C5FD' : 'var(--text-muted)',
            }}>
              {t === 'segregated' ? 'Per Run' : 'All Runs'}
            </span>
          </button>
        ))}

        {/* Run ID display — only on segregated tab */}
        {tab === 'segregated' && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Run:</span>
            {runsLoading ? <LoadingSpinner size={16} /> : (
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: '#93C5FD' }}>{selectedRun || '—'}</span>
            )}
            {selectedRun && (
              <span style={{ fontSize: 10, color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                Approved
              </span>
            )}
          </div>
        )}
      </div>

      {/* Main content */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {tab === 'segregated' ? (
          selectedRun ? <SegregatedDashboard key={selectedRun} runId={selectedRun} /> : null
        ) : (
          <AnalyticalDashboard />
        )}
      </main>
    </div>
  );
}
