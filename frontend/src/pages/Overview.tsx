import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { GlassCard } from '../components/ui/index';
import { pipelineApi } from '../lib/api';
import { Run } from '../lib/types';
import { StatusBadge, KpiCard } from '../components/ui/index';
import { formatDateTime } from '../lib/utils';

const STEPS = [
  { n: 1, icon: '📂', title: 'Input Data', desc: 'Upload CSV, generate synthetic, or connect external API' },
  { n: 2, icon: '🔍', title: 'Pre-Ingest Gate', desc: 'Validate schema, detect hard blocks and soft warnings' },
  { n: 3, icon: '⚡', title: 'Kafka Streaming', desc: '50ms/event streaming with rolling window buffer' },
  { n: 4, icon: '🤖', title: 'AI Agents', desc: '5 specialized agents analyze, detect, recommend' },
  { n: 5, icon: '👤', title: 'Human Review', desc: 'Clinical expert reviews AI report and approves' },
  { n: 6, icon: '📊', title: 'Dashboard', desc: 'Observability analytics and immutable audit trail' },
];

const PILLARS = [
  { icon: '⏱️', title: 'Freshness', desc: 'Event arrival latency, data recency vs baseline' },
  { icon: '📊', title: 'Volume', desc: 'Record counts, streaming event rates, window size' },
  { icon: '🔷', title: 'Schema', desc: 'Column presence, data types, null rates per column' },
  { icon: '📈', title: 'Distribution', desc: 'Statistical drift via KS-test, IQR outliers' },
  { icon: '🔗', title: 'Lineage', desc: 'Data source traceability, pipeline provenance' },
];

const WHATS_NEW = [
  'LangGraph multi-agent orchestration with 5 specialized agents',
  'Real-time Kafka streaming at 50ms per event',
  'Pre-ingest validation gate with hard blocks and soft warnings',
  'Microsoft Presidio PII/PHI masking (PERSON, EMAIL, PHONE, SSN)',
  'Human-in-the-Loop review with approval/rejection workflow',
  'Immutable append-only audit trail (FDA 21 CFR Part 11)',
  'Token usage tracking and GPT-4o cost estimation',
  'Confidence scoring with auto-retry on low scores',
];

export default function Overview() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    pipelineApi.getRecentRuns(5).then((d: any) => setRuns(d.runs || [])).catch(() => {});
  }, []);

  return (
    <div style={{ padding: '28px' }}>
          {/* Hero */}
          <div style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(6,182,212,0.05) 100%)', border: '1px solid var(--border-color)', borderRadius: 16, padding: '40px 48px', marginBottom: 28, position: 'relative', overflow: 'hidden', textAlign: 'center' }}>
            <div style={{ position: 'absolute', top: -40, right: -40, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.1) 0%, transparent 70%)' }} />
            <span style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 20, padding: '3px 12px', fontSize: 12, fontFamily: 'Space Grotesk', fontWeight: 700 }}>v6.0.0</span>
            <div className="animate-float" style={{ fontSize: 56, margin: '16px auto 20px' }}>🛡️</div>
            <h1 style={{ fontSize: 32, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 8 }}>Agentic AI Data Observability System</h1>
            <p style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 4 }}>Clinical Trials — Real-Time Kafka Streaming</p>
            <p className="gradient-text" style={{ fontSize: 14, fontWeight: 600, fontFamily: 'Space Grotesk', marginBottom: 24 }}>AI-powered. Human-governed. Compliance-first.</p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
              {['⚡ Real-time Streaming', '🤖 AI Agents (5)', '👤 Human-in-the-Loop', '🔒 Secure & Compliant', '🏠 Local Deployment'].map(f => (
                <span key={f} style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 20, padding: '5px 14px', fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'Space Grotesk' }}>{f}</span>
              ))}
            </div>
          </div>

          {/* How It Works */}
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 16 }}>How It Works</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 0, marginBottom: 32, position: 'relative' }}>
            {STEPS.map((step, i) => (
              <div key={step.n} style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
                <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 10, padding: '16px 14px', flex: 1, textAlign: 'center' }}>
                  <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-blue)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, fontFamily: 'Space Grotesk', margin: '0 auto 10px' }}>{step.n}</div>
                  <p style={{ fontSize: 20, marginBottom: 8 }}>{step.icon}</p>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>{step.title}</p>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{step.desc}</p>
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{ display: 'flex', alignItems: 'center', padding: '0 4px', marginTop: 40 }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: 16 }}>→</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Three columns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 28 }}>
            {/* Pillars */}
            <GlassCard>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 14 }}>5 Observability Pillars</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {PILLARS.map(p => (
                  <div key={p.title} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span style={{ fontSize: 18, flexShrink: 0 }}>{p.icon}</span>
                    <div>
                      <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{p.title}</p>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{p.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Architecture */}
            <GlassCard>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 14 }}>System Architecture</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                {[
                  { label: 'Data Sources', icon: '💾', color: '#06B6D4' },
                  { label: 'Pre-Ingest Validation', icon: '🔍', color: '#3B82F6' },
                  { label: 'Kafka Streaming', icon: '⚡', color: '#F59E0B' },
                  { label: 'AI Agents (LangGraph)', icon: '🤖', color: '#7C3AED' },
                  { label: 'HITL Review', icon: '👤', color: '#10B981' },
                  { label: 'Dashboard & Audit', icon: '📊', color: '#06B6D4' },
                ].map((item, i, arr) => (
                  <div key={item.label}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: `${item.color}10`, border: `1px solid ${item.color}25`, borderRadius: 8, padding: '8px 10px' }}>
                      <span style={{ fontSize: 14 }}>{item.icon}</span>
                      <span style={{ color: item.color, fontFamily: 'Space Grotesk', fontWeight: 600, fontSize: 11 }}>{item.label}</span>
                    </div>
                    {i < arr.length - 1 && <div style={{ width: 2, height: 6, background: 'var(--border-color)', margin: '2px auto' }} />}
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* What's New */}
            <GlassCard>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 14 }}>What's New in v4.0</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {WHATS_NEW.map(item => (
                  <div key={item} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <span style={{ color: '#10B981', flexShrink: 0, marginTop: 2 }}>✓</span>
                    <span style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{item}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* Recent Runs */}
          {runs.length > 0 && (
            <GlassCard style={{ marginBottom: 28 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 14 }}>Recent Pipeline Runs</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Run ID</th><th>Input Mode</th><th>Rows</th><th>Status</th><th>Started At</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r: Run) => (
                    <tr key={r.run_id}>
                      <td><span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: 'var(--accent-cyan)' }}>{r.run_id}</span></td>
                      <td style={{ color: 'var(--text-secondary)' }}>{r.input_mode}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{r.rows}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: 11 }}>{formatDateTime(r.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          )}

          {/* CTA */}
          <div style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(124,58,237,0.08) 100%)', border: '1px solid var(--border-color)', borderRadius: 16, padding: '32px 40px', textAlign: 'center' }}>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 8 }}>Designed for Life Sciences. Built for Trust.</p>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 20 }}>Ready to analyze your clinical trial data?</h2>
            <button onClick={() => navigate('/pipeline')} className="btn-primary" style={{ fontSize: 15, padding: '12px 32px' }}>
              Get Started → Run Pipeline
            </button>
          </div>
    </div>
  );
}
