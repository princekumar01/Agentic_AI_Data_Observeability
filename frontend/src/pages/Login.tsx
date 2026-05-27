import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authApi } from '../lib/api';
import { ROLES } from '../lib/utils';
import { LoadingSpinner, Toast } from '../components/ui/index';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<'login' | 'signup'>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [form, setForm] = useState({ username: 'admin', password: 'admin123', fullName: '', email: '', role: ROLES[0] });

  function showToast(msg: string) { setToast(msg); setTimeout(() => setToast(''), 3000); }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setError('');
    try {
      const res = await authApi.login(form.username, form.password);
      login(res.token, res.user);
      navigate('/overview');
    } catch (err: any) {
      setError(err.detail?.error || 'Invalid credentials');
    } finally { setLoading(false); }
  }

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setError('');
    try {
      const res = await authApi.signup({ fullName: form.fullName, username: form.username, email: form.email, password: form.password, role: form.role });
      login(res.token, res.user);
      navigate('/overview');
    } catch (err: any) {
      setError(err.detail?.error || 'Signup failed');
    } finally { setLoading(false); }
  }

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault(); setLoading(true);
    try {
      await authApi.forgotPassword(form.email);
      showToast('Reset instructions sent if email exists');
      setForgotMode(false);
    } catch {} finally { setLoading(false); }
  }

  const inp = (field: keyof typeof form, type = 'text', placeholder = '') => (
    <input type={type} placeholder={placeholder} value={form[field]}
      onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
      className="field" style={{ marginBottom: 12 }} required />
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', fontFamily: 'DM Sans' }}>
      {/* Left Panel */}
      <div style={{ flex: 1, background: 'linear-gradient(135deg, #060D1A 0%, #0A1628 40%, #061525 100%)', padding: '40px 60px', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
        {/* Background decoration */}
        <div style={{ position: 'absolute', top: -100, right: -100, width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%)' }} />
        <div style={{ position: 'absolute', bottom: -100, left: -50, width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(6,182,212,0.05) 0%, transparent 70%)' }} />

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 60 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>🏥</div>
          <div>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'Space Grotesk', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Clinical Trials</p>
            <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>AI Observability Platform</p>
          </div>
          <span style={{ marginLeft: 16, background: 'rgba(16,185,129,0.15)', color: '#10B981', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 20, padding: '2px 10px', fontSize: 11, fontFamily: 'Space Grotesk', fontWeight: 700 }}>v6.0.0</span>
        </div>

        {/* Hero */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div className="animate-float" style={{ fontSize: 72, marginBottom: 24, textAlign: 'center' }}>🛡️</div>
          <h1 style={{ fontSize: 32, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 16, lineHeight: 1.2 }}>
            Agentic AI Data<br />Observability System
          </h1>
          <p style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 8 }}>
            Clinical Trials — Real-Time Kafka Streaming
          </p>
          <p className="gradient-text" style={{ fontSize: 14, fontWeight: 600, fontFamily: 'Space Grotesk', marginBottom: 40 }}>
            AI-powered. Human-governed. Compliance-first.
          </p>

          {/* Feature pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 48 }}>
            {['🔒 Secure & Compliant', '⚡ Real-time Streaming', '🤖 5 AI Agents', '👤 Human-in-the-Loop', '🏠 Local Deployment'].map(f => (
              <span key={f} style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 20, padding: '6px 14px', fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'Space Grotesk' }}>{f}</span>
            ))}
          </div>

          {/* Feature cards 2x2 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { icon: '🔐', title: 'Secure & Compliant', desc: 'FDA 21 CFR Part 11, HIPAA, ICH E6 GCP' },
              { icon: '⚡', title: 'Real-time Streaming', desc: 'Apache Kafka at 50ms per event' },
              { icon: '🤖', title: 'AI Agents', desc: '5 specialized LangGraph agents' },
              { icon: '👤', title: 'Human-in-the-Loop', desc: 'Clinical expert review & approval' },
            ].map(f => (
              <div key={f.title} style={{ background: 'rgba(13,30,53,0.6)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 14 }}>
                <p style={{ fontSize: 18, marginBottom: 6 }}>{f.icon}</p>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'Space Grotesk' }}>{f.title}</p>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>

        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 40 }}>
          🔒 Your data stays within your environment. No cloud storage.
        </p>
      </div>

      {/* Right Panel */}
      <div style={{ width: 480, background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 48px', borderLeft: '1px solid var(--border-color)' }}>
        <div style={{ width: '100%' }}>
          {forgotMode ? (
            <div>
              <h2 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 8 }}>Reset Password</h2>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 28 }}>Enter your email to receive reset instructions</p>
              <form onSubmit={handleForgot}>
                {inp('email', 'email', 'Email address')}
                <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                  {loading && <LoadingSpinner size="sm" />} Send Reset Link
                </button>
              </form>
              <button onClick={() => setForgotMode(false)} style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', marginTop: 16, fontSize: 13, fontFamily: 'Space Grotesk' }}>← Back to Sign In</button>
            </div>
          ) : (
            <>
              {/* Tabs */}
              <div style={{ display: 'flex', background: 'rgba(6,13,26,0.6)', borderRadius: 10, padding: 4, marginBottom: 28 }}>
                {(['login', 'signup'] as const).map(t => (
                  <button key={t} onClick={() => { setTab(t); setError(''); }} style={{ flex: 1, padding: '8px 0', borderRadius: 8, border: 'none', cursor: 'pointer', fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 600, transition: 'all 0.2s', background: tab === t ? 'var(--accent-blue)' : 'transparent', color: tab === t ? '#fff' : 'var(--text-muted)' }}>
                    {t === 'login' ? 'Sign In' : 'Sign Up'}
                  </button>
                ))}
              </div>

              {tab === 'login' ? (
                <>
                  <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Welcome Back</h2>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>Sign in to access the observability platform</p>
                  {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#EF4444', fontSize: 13 }}>{error}</div>}
                  <form onSubmit={handleLogin}>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Username</label>
                    <input className="field" style={{ marginBottom: 16 }} value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} placeholder="Username" required />
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Password</label>
                    <div style={{ position: 'relative', marginBottom: 8 }}>
                      <input className="field" type={showPw ? 'text' : 'password'} value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Password" required style={{ paddingRight: 44 }} />
                      <button type="button" onClick={() => setShowPw(!showPw)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 16 }}>{showPw ? '🙈' : '👁'}</button>
                    </div>
                    <div style={{ textAlign: 'right', marginBottom: 20 }}>
                      <button type="button" onClick={() => setForgotMode(true)} style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', fontSize: 12, fontFamily: 'Space Grotesk' }}>Forgot Password?</button>
                    </div>
                    <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                      {loading && <LoadingSpinner size="sm" />} Sign In
                    </button>

                  </form>
                  <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-muted)' }}>
                    Don't have an account? <button onClick={() => setTab('signup')} style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', fontFamily: 'Space Grotesk', fontSize: 13 }}>Sign Up</button>
                  </p>
                </>
              ) : (
                <>
                  <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Create Account</h2>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24 }}>Join the observability platform</p>
                  {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#EF4444', fontSize: 13 }}>{error}</div>}
                  <form onSubmit={handleSignup}>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Full Name</label>
                    {inp('fullName', 'text', 'Dr. Jane Smith')}
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Username</label>
                    {inp('username', 'text', 'jane.smith')}
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Email</label>
                    {inp('email', 'email', 'jane.smith@clinicaltrials.ai')}
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Password</label>
                    {inp('password', 'password', 'Secure password')}
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'Space Grotesk', marginBottom: 4 }}>Role</label>
                    <select className="field" style={{ marginBottom: 20 }} value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                      {loading && <LoadingSpinner size="sm" />} Create Account
                    </button>
                  </form>
                  <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-muted)' }}>
                    Already have an account? <button onClick={() => setTab('login')} style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', fontFamily: 'Space Grotesk', fontSize: 13 }}>Sign In</button>
                  </p>
                </>
              )}
            </>
          )}
        </div>
      </div>
      {toast && <Toast message={toast} type="info" />}
    </div>
  );
}
