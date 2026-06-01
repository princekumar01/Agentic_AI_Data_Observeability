import { useState, useEffect, useCallback } from 'react';
import { Bell, Filter, Search, Clock, X, Eye } from 'lucide-react';
import { alertsApi } from '../lib/api';
import { Alert } from '../lib/types';
import { GlassCard, SeverityIcon, LoadingSpinner } from '../components/ui';
import { formatDateTime } from '../lib/utils';

const SEVERITY_ORDER = ['critical', 'warning', 'total'];

const SEV_COLORS: Record<string, { color: string; bg: string; border: string; badgeBg: string; badgeText: string }> = {
  critical: { color: '#f87171', bg: 'rgba(239,68,68,0.06)', border: 'rgba(239,68,68,0.4)', badgeBg: 'rgba(239,68,68,0.15)', badgeText: '#fca5a5' },
  warning:  { color: '#fb923c', bg: 'rgba(249,115,22,0.06)', border: 'rgba(249,115,22,0.4)', badgeBg: 'rgba(249,115,22,0.15)', badgeText: '#fdba74' },
  high:     { color: '#f59e0b', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.4)', badgeBg: 'rgba(245,158,11,0.15)', badgeText: '#fcd34d' },
  total:    { color: '#60a5fa', bg: 'rgba(59,130,246,0.06)', border: 'rgba(59,130,246,0.3)', badgeBg: 'rgba(59,130,246,0.15)', badgeText: '#93c5fd' },
  medium:   { color: '#facc15', bg: 'rgba(234,179,8,0.06)',  border: 'rgba(234,179,8,0.3)',  badgeBg: 'rgba(234,179,8,0.15)',  badgeText: '#fde047' },
  low:      { color: '#60a5fa', bg: 'rgba(59,130,246,0.06)', border: 'rgba(59,130,246,0.3)', badgeBg: 'rgba(59,130,246,0.15)', badgeText: '#93c5fd' },
  info:     { color: '#4ade80', bg: 'rgba(34,197,94,0.06)', border: 'rgba(34,197,94,0.3)', badgeBg: 'rgba(34,197,94,0.15)', badgeText: '#86efac' },
};

function sevColors(severity: string) {
  return SEV_COLORS[severity?.toLowerCase()] ?? SEV_COLORS.low;
}

const STATUS_COLORS: Record<string, string> = {
  active: '#f87171',
  acknowledged: '#facc15',
  escalated: '#c084fc',
  resolved: '#4ade80',
};

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [dropdownSeverity, setDropdownSeverity] = useState<string>('all');
  const fetchAlerts = useCallback(async () => {
    try {
      const data = await alertsApi.getAlerts({
        severity: filterSeverity !== 'all' ? filterSeverity : undefined,
        status: filterStatus !== 'all' ? filterStatus : undefined,
      });
      setAlerts(data);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [filterSeverity, filterStatus]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);
  useEffect(() => {
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

const handleMarkRead = async (alertId: string) => {
    try { await alertsApi.markRead(alertId); fetchAlerts(); } catch { }
  };

  const filtered = alerts.filter(a => {
    const matchSearch = !search || a.title.toLowerCase().includes(search.toLowerCase()) || a.message?.toLowerCase().includes(search.toLowerCase());
    const matchDropdown = dropdownSeverity === 'all' || a.severity === dropdownSeverity;
    return matchSearch && matchDropdown;
  });

  const counts = {
    critical: alerts.filter(a => a.severity === 'critical').length,
    warning:  alerts.filter(a => a.severity === 'warning').length,
    total:    alerts.length,
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      <LoadingSpinner size="lg" />
    </div>
  );

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
            <Bell size={22} style={{ color: '#f87171' }} /> Alert Center
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'DM Sans', margin: '4px 0 0' }}>{alerts.length} total alerts · Auto-refreshes every 10s</p>
        </div>
      </div>

      {/* Severity Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 200px)', gap: 12, marginBottom: 20, justifyContent: 'center' }}>
        {SEVERITY_ORDER.map(sev => {
          const c = SEV_COLORS[sev];
          const count = counts[sev as keyof typeof counts];
          const isActive = filterSeverity === sev;
          return (
            <button
              key={sev}
              onClick={() => {}}
              style={{ padding: 12, borderRadius: 12, border: `1px solid ${isActive ? c.border : 'rgba(51,65,85,0.5)'}`, background: isActive ? c.bg : 'rgba(15,23,42,0.5)', cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'capitalize', color: isActive ? c.color : 'var(--text-muted)', fontFamily: 'Space Grotesk' }}>{sev}</span>
                <SeverityIcon severity={sev} size={14} />
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'Space Grotesk', color: isActive ? c.color : 'var(--text-primary)' }}>{count}</div>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search alerts by id"
            className="field"
            style={{ paddingLeft: 30, width: '100%', boxSizing: 'border-box' }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Filter size={13} style={{ color: 'var(--text-muted)' }} />
          {['all'].map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              style={{ padding: '5px 10px', borderRadius: 8, fontSize: 11, textTransform: 'capitalize', cursor: 'pointer', transition: 'all 0.15s', background: filterStatus === s ? 'var(--accent-blue)' : 'var(--bg-secondary)', color: filterStatus === s ? '#fff' : 'var(--text-secondary)', border: `1px solid ${filterStatus === s ? 'var(--accent-blue)' : 'var(--border-color)'}`, fontFamily: 'Space Grotesk' }}
            >
              {s}
            </button>
          ))}
          <select
            value={dropdownSeverity}
            onChange={e => setDropdownSeverity(e.target.value)}
            style={{ padding: '5px 10px', borderRadius: 8, fontSize: 11, cursor: 'pointer', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', fontFamily: 'Space Grotesk', outline: 'none' }}
          >
            <option value="all">All Severity</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="warning">Warning</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </select>
        </div>
      </div>

      {/* Two-panel layout */}
      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 340px)', minHeight: 320 }}>
        {/* Alert list */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          <GlassCard style={{ flex: 1, overflowY: 'auto', padding: 0 }}>
            {filtered.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '48px 0', color: 'var(--text-muted)' }}>
                <Bell size={36} style={{ marginBottom: 12, opacity: 0.4 }} />
                <p style={{ fontSize: 13 }}>No alerts match your filters</p>
              </div>
            ) : (
              <div>
                {filtered.map((alert, i) => {
                  const c = sevColors(alert.severity);
                  const isSelected = selected?.id === alert.id;
                  return (
                    <div
                      key={alert.id}
                      onClick={() => { setSelected(alert); if (!alert.read) handleMarkRead(alert.id); }}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 16px', cursor: 'pointer', transition: 'background 0.15s',
                        background: isSelected ? 'rgba(51,65,85,0.4)' : 'transparent',
                        borderBottom: i < filtered.length - 1 ? '1px solid rgba(30,41,59,0.5)' : 'none',
                        borderLeft: !alert.read ? '2px solid var(--accent-blue)' : '2px solid transparent',
                      }}
                    >
                      <SeverityIcon severity={alert.severity} size={16} className="shrink-0" />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: !alert.read ? 'var(--text-primary)' : 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{alert.title}</span>
                          <span style={{ flexShrink: 0, fontSize: 10, padding: '1px 6px', borderRadius: 4, border: `1px solid ${c.border}`, background: c.badgeBg, color: c.badgeText, textTransform: 'capitalize' }}>{alert.severity}</span>
                        </div>
                        <p style={{ fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0 }}>{alert.message}</p>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                          <span style={{ fontSize: 10, color: STATUS_COLORS[alert.status] || 'var(--text-muted)', textTransform: 'capitalize' }}>{alert.status}</span>
                          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>·</span>
                          <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Clock size={9} /> {formatDateTime(alert.triggered_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Detail panel */}
        <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          {selected ? (
            <GlassCard style={{ flex: 1, overflowY: 'auto', padding: 0, display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>Alert Details</span>
                <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}>
                  <X size={16} />
                </button>
              </div>
              <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
                    <SeverityIcon severity={selected.severity} size={16} className="shrink-0" />
                    <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: 0, lineHeight: 1.4 }}>{selected.title}</h3>
                  </div>
                  {(() => {
                    const c = sevColors(selected.severity);
                    return (
                      <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, border: `1px solid ${c.border}`, background: c.badgeBg, color: c.badgeText }}>{selected.severity.toUpperCase()}</span>
                    );
                  })()}
                </div>

                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Message</div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>{selected.message}</p>
                </div>

                {selected.source && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Source</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono' }}>{selected.source}</div>
                  </div>
                )}

                {selected.run_id && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Run ID</div>
                    <div style={{ fontSize: 12, color: 'var(--accent-cyan)', fontFamily: 'JetBrains Mono' }}>{selected.run_id}</div>
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Status</div>
                    <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'capitalize', color: STATUS_COLORS[selected.status] || 'var(--text-secondary)' }}>{selected.status}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Category</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{selected.category || '—'}</div>
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Triggered At</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{formatDateTime(selected.triggered_at)}</div>
                </div>

                {selected.acknowledged_at && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Acknowledged At</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{formatDateTime(selected.acknowledged_at)}</div>
                  </div>
                )}

                {selected.recommendation && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Recommended Action</div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(6,13,26,0.5)', padding: '8px 10px', borderRadius: 8, margin: 0 }}>{selected.recommendation}</p>
                  </div>
                )}


              </div>
            </GlassCard>
          ) : (
            <GlassCard style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>
                <Eye size={28} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
                <p style={{ fontSize: 13, margin: 0 }}>Select an alert to view details</p>
              </div>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );
}
