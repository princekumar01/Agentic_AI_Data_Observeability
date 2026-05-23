import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import Login from './pages/Login';
import Overview from './pages/Overview';
import Pipeline from './pages/Pipeline';
import Streaming from './pages/Streaming';
import Review from './pages/Review';
import Dashboard from './pages/Dashboard';
import Alerts from './pages/Alerts';
import Audit from './pages/Audit';

function AppLayout({ children, title, subtitle }: { children: React.ReactNode; title?: string; subtitle?: string }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <Sidebar />
      <div style={{ marginLeft: 220, flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden', height: '100vh' }}>
        <Topbar title={title} subtitle={subtitle} />
        <main style={{ flex: 1, overflowY: 'auto' }}>
          {children}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<AppLayout title="Overview" subtitle="System status and quick start"><Overview /></AppLayout>} />
            <Route path="/overview" element={<AppLayout title="Overview" subtitle="System status and quick start"><Overview /></AppLayout>} />
            <Route path="/pipeline" element={<AppLayout title="Pipeline" subtitle="Configure and run the observability pipeline"><Pipeline /></AppLayout>} />
            <Route path="/streaming" element={<AppLayout title="Streaming Pipeline" subtitle="Live Kafka stream monitor"><Streaming /></AppLayout>} />
            <Route path="/review" element={<AppLayout title="Review" subtitle="Human-in-the-Loop review"><Review /></AppLayout>} />
            <Route path="/dashboard" element={<AppLayout title="Dashboard" subtitle="Analytics and observability"><Dashboard /></AppLayout>} />
            <Route path="/dashboard/:run_id" element={<AppLayout title="Dashboard" subtitle="Analytics and observability"><Dashboard /></AppLayout>} />
            <Route path="/alerts" element={<AppLayout title="Alerts" subtitle="Alert center"><Alerts /></AppLayout>} />
            <Route path="/audit" element={<AppLayout title="Audit Trail" subtitle="Immutable event log"><Audit /></AppLayout>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
