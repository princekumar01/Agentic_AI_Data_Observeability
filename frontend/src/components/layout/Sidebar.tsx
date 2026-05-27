import { NavLink, useLocation } from 'react-router-dom';
import { useActiveRun, useAlerts } from '../../hooks/index';
import { StatusBadge } from '../ui/index';
import { formatDateTime } from '../../lib/utils';

const NAV = [
  { group: 'MAIN', items: [{ to: '/overview', icon: '⊡', label: 'Overview' }] },
  { group: 'PIPELINE', items: [
    { to: '/pipeline', icon: '◈', label: 'Pipeline' },
    { to: '/streaming', icon: '◉', label: 'Streaming Pipeline' },
  ]},
  { group: 'OBSERVABILITY', items: [
    { to: '/review', icon: '◫', label: 'Review (HITL)' },
    { to: '/result', icon: '◇', label: 'Result' },
  ]},
  { group: 'GOVERNANCE', items: [
    { to: '/alerts', icon: '◬', label: 'Alerts' },
    { to: '/audit', icon: '◪', label: 'Audit Trail' },
  ]},
];

export default function Sidebar() {
  const location = useLocation();
  const activeRun = useActiveRun();
  const { unreadCount } = useAlerts();

  return (
    <aside style={{
      width: 220, flexShrink: 0,
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border-color)',
      display: 'flex', flexDirection: 'column',
      height: '100vh', position: 'fixed', left: 0, top: 0, zIndex: 100,
      overflowY: 'auto',
    }}>
      {/* Logo */}
      <div style={{ padding: '20px 16px', borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>🏥</div>
          <div>
            <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-blue)', fontFamily: 'Space Grotesk', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Clinical Trials</p>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'Space Grotesk' }}>AI Observability</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 8px' }}>
        {NAV.map(group => (
          <div key={group.group} style={{ marginBottom: 8 }}>
            <p className="section-label" style={{ padding: '8px 10px 4px', fontSize: 10 }}>{group.group}</p>
            {group.items.map(item => {
              const isActive = location.pathname === item.to || location.pathname.startsWith(item.to + '/');
              return (
                <NavLink key={item.to} to={item.to} style={{ textDecoration: 'none' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 10px', borderRadius: 6, marginBottom: 2,
                    borderLeft: isActive ? '3px solid var(--accent-blue)' : '3px solid transparent',
                    background: isActive ? 'rgba(59,130,246,0.12)' : 'transparent',
                    color: isActive ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    fontSize: 13, fontFamily: 'Space Grotesk', fontWeight: isActive ? 600 : 400,
                    transition: 'all 0.15s', cursor: 'pointer',
                  }}
                  onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'rgba(59,130,246,0.06)'; }}
                  onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                  >
                    <span style={{ fontSize: 15 }}>{item.icon}</span>
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.label === 'Alerts' && unreadCount > 0 && (
                      <span style={{ background: 'var(--accent-red)', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 10, fontWeight: 700 }}>
                        {unreadCount}
                      </span>
                    )}
                  </div>
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Current Run Widget */}
      <div style={{ padding: '12px 12px 16px', borderTop: '1px solid var(--border-color)' }}>
        <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'Space Grotesk', marginBottom: 8 }}>Current Run</p>
        {activeRun?.run_id ? (
          <div style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 8, padding: 10 }}>
            <p style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: 'var(--accent-cyan)', marginBottom: 6, wordBreak: 'break-all' }}>{activeRun.run_id}</p>
            <StatusBadge status={activeRun.status} />
            {activeRun.started_at && (
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
                Started {formatDateTime(activeRun.started_at)}
              </p>
            )}
            <NavLink to="/pipeline" style={{ display: 'block', marginTop: 8, fontSize: 11, color: 'var(--accent-blue)', textDecoration: 'none', fontFamily: 'Space Grotesk' }}>View Run Details →</NavLink>
          </div>
        ) : (
          <div style={{ background: 'rgba(6,13,26,0.5)', borderRadius: 8, padding: 10, textAlign: 'center' }}>
            <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>No active run</p>
          </div>
        )}
      </div>
    </aside>
  );
}
