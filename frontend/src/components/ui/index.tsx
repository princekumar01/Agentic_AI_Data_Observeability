import { AgentStatus } from '../../lib/types';
import { confidenceColor } from '../../lib/utils';

// ── StatusBadge ───────────────────────────────────────────────────────────────
const STATUS_CFG: Record<string, { color: string; bg: string }> = {
  approved:       { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  pending_review: { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  rejected:       { color: '#EF4444', bg: 'rgba(239,68,68,0.12)' },
  running:        { color: '#3B82F6', bg: 'rgba(59,130,246,0.12)' },
  completed:      { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  failed:         { color: '#EF4444', bg: 'rgba(239,68,68,0.12)' },
  acknowledged:   { color: '#06B6D4', bg: 'rgba(6,182,212,0.12)' },
  escalated:      { color: '#8B5CF6', bg: 'rgba(139,92,246,0.12)' },
  resolved:       { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  active:         { color: '#EF4444', bg: 'rgba(239,68,68,0.12)' },
  online:         { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  healthy:        { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  success:        { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  error:          { color: '#EF4444', bg: 'rgba(239,68,68,0.12)' },
  idle:           { color: '#4A6FA5', bg: 'rgba(74,111,165,0.12)' },
  COMPLETED:      { color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
  RUNNING:        { color: '#3B82F6', bg: 'rgba(59,130,246,0.12)' },
  PENDING:        { color: '#4A6FA5', bg: 'rgba(74,111,165,0.12)' },
};

export function StatusBadge({ status, size = 'sm' }: { status: string; size?: 'sm' | 'md' }) {
  const key = status?.toLowerCase().replace(' ', '_');
  const cfg = STATUS_CFG[status] || STATUS_CFG[key] || { color: '#8BACC8', bg: 'rgba(139,172,200,0.12)' };
  const isLive = ['running','RUNNING'].includes(status);
  const px = size === 'sm' ? '2px 8px' : '4px 12px';
  const fs = size === 'sm' ? 11 : 13;
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:5, background:cfg.bg, color:cfg.color,
      border:`1px solid ${cfg.color}30`, borderRadius:20, padding:px, fontSize:fs,
      fontFamily:'Space Grotesk', fontWeight:600, whiteSpace:'nowrap' }}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:cfg.color, flexShrink:0,
        animation: isLive ? 'blink-dot 1.4s ease-in-out infinite' : 'none' }} />
      {status}
    </span>
  );
}

// ── KpiCard ───────────────────────────────────────────────────────────────────
export function KpiCard({ label, value, icon, trend, trendLabel, trendInvert }:
  { label: string; value: string | number; icon?: React.ReactNode; trend?: number; trendLabel?: string; trendInvert?: boolean }) {
  const positive = trendInvert ? (trend ?? 0) < 0 : (trend ?? 0) > 0;
  const trendColor = trend === undefined ? '' : positive ? '#10B981' : '#EF4444';
  const arrow = trend === undefined ? '' : (trend > 0 ? '▲' : '▼');
  return (
    <div className="glass-card" style={{ padding:20, cursor:'default', transition:'transform 0.2s' }}
      onMouseEnter={e=>(e.currentTarget.style.transform='translateY(-2px)')}
      onMouseLeave={e=>(e.currentTarget.style.transform='translateY(0)')}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
        <p style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.08em', color:'var(--text-muted)', fontFamily:'Space Grotesk' }}>{label}</p>
        {icon}
      </div>
      <p style={{ fontSize:28, fontWeight:700, color:'var(--text-primary)', fontFamily:'Space Grotesk', lineHeight:1 }}>{value}</p>
      {trend !== undefined && (
        <p style={{ fontSize:12, color:trendColor, marginTop:8, fontWeight:500 }}>
          {arrow} {Math.abs(trend).toFixed(1)}% {trendLabel || 'vs last period'}
        </p>
      )}
    </div>
  );
}

// ── GlassCard ─────────────────────────────────────────────────────────────────
export function GlassCard({ children, padding, className = '', style = {} }:
  { children: React.ReactNode; padding?: number | string; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={`glass-card ${className}`} style={{ ...(padding !== undefined ? { padding } : {}), ...style }}>
      {children}
    </div>
  );
}

// ── LoadingSpinner ─────────────────────────────────────────────────────────────
export function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const px = size === 'sm' ? 16 : size === 'lg' ? 40 : 24;
  return (
    <svg width={px} height={px} viewBox="0 0 24 24" fill="none"
      style={{ animation:'spin-slow 0.8s linear infinite', flexShrink:0 }}>
      <circle cx="12" cy="12" r="10" stroke="var(--accent-blue)" strokeWidth="2" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--accent-blue)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, width = 600 }:
  { open: boolean; onClose: () => void; title: string; children: React.ReactNode; width?: number }) {
  if (!open) return null;
  return (
    <div style={{ position:'fixed', inset:0, zIndex:1000, background:'rgba(6,13,26,0.85)',
      display:'flex', alignItems:'center', justifyContent:'center', backdropFilter:'blur(4px)' }}
      onClick={onClose}>
      <div className="glass-card animate-fade-up" style={{ width, maxWidth:'95vw', maxHeight:'90vh', overflowY:'auto' }}
        onClick={e=>e.stopPropagation()}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
          padding:'16px 24px', borderBottom:'1px solid var(--border-color)' }}>
          <h3 style={{ fontSize:16, fontWeight:600, color:'var(--text-primary)', fontFamily:'Space Grotesk' }}>{title}</h3>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'var(--text-muted)',
            cursor:'pointer', fontSize:20, lineHeight:1, padding:4 }}>✕</button>
        </div>
        <div style={{ padding:24 }}>{children}</div>
      </div>
    </div>
  );
}

// ── ConfidenceBadge ───────────────────────────────────────────────────────────
export function ConfidenceBadge({ score }: { score: number }) {
  const color = confidenceColor(score);
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:4,
      background:`${color}18`, color, border:`1px solid ${color}30`,
      borderRadius:20, padding:'2px 8px', fontSize:11, fontFamily:'Space Grotesk', fontWeight:700 }}>
      {score}%
    </span>
  );
}

// ── PillarCard ────────────────────────────────────────────────────────────────
export function PillarCard({ label, icon, score, color, findings, status }:
  { label: string; icon: string; score: number; color: string; findings: number; status: string }) {
  const bg = `${color}12`;
  const border = `${color}30`;
  const statusLabel = status === 'normal' ? 'Normal' : status === 'warning' ? 'Warning' : 'Critical';
  const statusColor = status === 'normal' ? '#10B981' : status === 'warning' ? '#F59E0B' : '#EF4444';
  return (
    <div style={{ background:bg, border:`1px solid ${border}`, borderRadius:12, padding:'16px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
        <span style={{ fontSize:20 }}>{icon}</span>
        <span style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', fontFamily:'Space Grotesk', lineHeight:1.3 }}>{label}</span>
      </div>
      <div style={{ fontSize:26, fontWeight:700, color, fontFamily:'Space Grotesk', marginBottom:4 }}>{score}</div>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <span style={{ fontSize:11, color:'var(--text-muted)' }}>{findings} finding{findings !== 1 ? 's' : ''}</span>
        <span style={{ fontSize:10, color:statusColor, fontWeight:600, background:`${statusColor}15`,
          border:`1px solid ${statusColor}30`, borderRadius:8, padding:'1px 6px' }}>{statusLabel}</span>
      </div>
    </div>
  );
}

// ── SeverityIcon ──────────────────────────────────────────────────────────────
export function SeverityIcon({ severity, size = 16, className = '' }:
  { severity: string; size?: number; className?: string }) {
  const s = severity?.toLowerCase();
  const color = s === 'critical' ? '#EF4444' : s === 'high' ? '#F59E0B' : s === 'medium' ? '#3B82F6' : '#10B981';
  const symbol = s === 'critical' ? '⬤' : s === 'high' ? '▲' : s === 'medium' ? '◆' : '●';
  return <span style={{ color, fontSize: size * 0.75 }} className={className}>{symbol}</span>;
}

// ── AgentCard (Streaming agent status card) ───────────────────────────────────
export function AgentCard({ agent }: { agent: AgentStatus }) {
  const statusColor = agent.status === 'COMPLETED' ? '#10B981' : agent.status === 'RUNNING' ? '#3B82F6' : '#4A6FA5';
  const confColor = confidenceColor(agent.confidence);
  return (
    <div className="glass-card" style={{ padding:14 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
        <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', fontFamily:'Space Grotesk', lineHeight:1.3 }}>{agent.name}</div>
        <span style={{ width:7, height:7, borderRadius:'50%', background:statusColor, flexShrink:0, marginTop:3,
          boxShadow: agent.status === 'RUNNING' ? `0 0 6px ${statusColor}` : 'none',
          animation: agent.status === 'RUNNING' ? 'blink-dot 1.4s ease-in-out infinite' : 'none' }} />
      </div>
      <div style={{ fontSize:10, color:'var(--text-muted)', marginBottom:10, fontFamily:'JetBrains Mono' }}>{agent.status}</div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11 }}>
        <div>
          <div style={{ color:'var(--text-muted)', marginBottom:2 }}>Confidence</div>
          <div style={{ color:confColor, fontWeight:700, fontFamily:'Space Grotesk' }}>{agent.confidence}%</div>
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ color:'var(--text-muted)', marginBottom:2 }}>Inferences</div>
          <div style={{ color:'var(--text-primary)', fontWeight:600 }}>{agent.inferences}</div>
        </div>
      </div>
      <div style={{ marginTop:8, height:2, background:'rgba(255,255,255,0.06)', borderRadius:2 }}>
        <div style={{ height:'100%', borderRadius:2, background:confColor, width:`${agent.confidence}%`, transition:'width 0.6s ease' }} />
      </div>
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────
export function Toast({ message, type = 'info' }: { message: string; type?: 'success' | 'error' | 'info' }) {
  const colors = { success:'#10B981', error:'#EF4444', info:'#3B82F6' };
  return (
    <div className="toast" style={{ borderLeft:`3px solid ${colors[type]}`, display:'flex', alignItems:'center', gap:10 }}>
      <span style={{ color:colors[type], fontSize:16 }}>
        {type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}
      </span>
      <span style={{ fontSize:13, color:'var(--text-primary)' }}>{message}</span>
    </div>
  );
}
