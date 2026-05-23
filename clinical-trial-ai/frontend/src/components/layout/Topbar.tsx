import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useAlerts } from '../../hooks/index';
import { systemApi, authApi } from '../../lib/api';
import { SystemStatus } from '../../lib/types';

interface TopbarProps {
  title?: string;
  subtitle?: string;
  badge?: { label: string; color: string };
}

export default function Topbar({ title, subtitle, badge }: TopbarProps) {
  const { user, logout } = useAuth();
  const { unreadCount } = useAlerts();
  const navigate = useNavigate();
  const [now, setNow] = useState(new Date());
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    systemApi.status().then(setSysStatus).catch(() => {});
    const id = setInterval(() => systemApi.status().then(setSysStatus).catch(() => {}), 30000);
    return () => clearInterval(id);
  }, []);

  async function handleLogout() {
    try { await authApi.logout(); } catch {}
    logout();
  }

  return (
    <header style={{
      height: 56, background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border-color)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', position: 'sticky', top: 0, zIndex: 50,
    }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h1 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{title}</h1>
            {badge && (
              <span style={{ background: `${badge.color}18`, color: badge.color, border: `1px solid ${badge.color}30`, borderRadius: 20, padding: '1px 8px', fontSize: 10, fontFamily: 'Space Grotesk', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {badge.label}
              </span>
            )}
          </div>
          {subtitle && <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{subtitle}</p>}
        </div>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* System Status */}
        {sysStatus && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 20, padding: '4px 10px' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', animation: 'blink-dot 2s ease-in-out infinite' }} />
            <span style={{ fontSize: 11, color: '#10B981', fontFamily: 'Space Grotesk', fontWeight: 600 }}>System Healthy</span>
          </div>
        )}

        {/* Clock */}
        <span style={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: 'var(--text-muted)' }}>
          {now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} {now.toLocaleTimeString('en-US', { hour12: false })}
        </span>

        {/* Alerts Bell */}
        <button onClick={() => navigate('/alerts')} style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', color: 'var(--text-secondary)', padding: 4 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {unreadCount > 0 && (
            <span style={{ position: 'absolute', top: 0, right: 0, background: 'var(--accent-red)', color: '#fff', borderRadius: '50%', width: 14, height: 14, fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
              {unreadCount}
            </span>
          )}
        </button>

        {/* User chip */}
        {user && (
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowUserMenu(!showUserMenu)} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(59,130,246,0.08)', border: '1px solid var(--border-color)', borderRadius: 20, padding: '4px 12px 4px 4px', cursor: 'pointer' }}>
              <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent-blue)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, fontFamily: 'Space Grotesk', flexShrink: 0 }}>
                {user.avatar_initials}
              </span>
              <div style={{ textAlign: 'left' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', lineHeight: 1.2 }}>{user.fullName}</p>
                <p style={{ fontSize: 10, color: 'var(--text-muted)' }}>{user.role}</p>
              </div>
            </button>
            {showUserMenu && (
              <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 8, background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 8, minWidth: 160, zIndex: 200, boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
                <button onClick={handleLogout} style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-red)', fontSize: 13, fontFamily: 'Space Grotesk', padding: '8px 12px', textAlign: 'left', borderRadius: 6 }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.1)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
