import { useState, useEffect } from 'react';
import { Lock, BarChart2, TrendingUp, Activity, AlertTriangle, CheckCircle, Cpu, DollarSign, Clock, ChevronRight } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import { dashboardApi } from '../lib/api';
import { GlassCard, KpiCard, PillarCard, LoadingSpinner } from '../components/ui';
import {
  PipelineRunsChart, SeverityPieChart, AnomaliesTrendChart,
  TokenCostChart, RunStatusPieChart
} from '../components/charts';
import { formatDateTime } from '../lib/utils';

const PILLAR_DEFS = [
  { key: 'data_integrity', label: 'Data Integrity', icon: '🔒', color: '#3B82F6' },
  { key: 'safety_monitoring', label: 'Safety Monitoring', icon: '🛡️', color: '#10B981' },
  { key: 'protocol_compliance', label: 'Protocol Compliance', icon: '📋', color: '#8B5CF6' },
  { key: 'statistical_validity', label: 'Statistical Validity', icon: '📊', color: '#F59E0B' },
  { key: 'operational_efficiency', label: 'Operational Efficiency', icon: '⚙️', color: '#06B6D4' },
];

export default function Dashboard() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<any>(null);
  const [runsOverTime, setRunsOverTime] = useState<any[]>([]);
  const [anomaliesBySeverity, setAnomaliesBySeverity] = useState<any[]>([]);
  const [agentsPerf, setAgentsPerf] = useState<any[]>([]);
  const [tokenUsage, setTokenUsage] = useState<any[]>([]);
  const [pipelineHealth, setPipelineHealth] = useState<any>(null);
  const [anomaliesTrend, setAnomaliesTrend] = useState<any[]>([]);
  const [topAnomalyTypes, setTopAnomalyTypes] = useState<any[]>([]);
  const [runStatusDist, setRunStatusDist] = useState<any[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [lockReason, setLockReason] = useState('');

  useEffect(() => {
    const fetchAll = async () => {
      try {
        setLoading(true);
        const [sum, rot, abs, ap, tu, ph, at, tat, rsd, ra] = await Promise.all([
          dashboardApi.getSummary(),
          dashboardApi.getPipelineRunsOverTime(),
          dashboardApi.getAnomaliesBySeverity(),
          dashboardApi.getAgentsPerformance(),
          dashboardApi.getTokenUsage(),
          dashboardApi.getPipelineHealth(),
          dashboardApi.getAnomaliesTrend(),
          dashboardApi.getTopAnomalyTypes(),
          dashboardApi.getRunStatusDistribution(),
          dashboardApi.getRecentAlerts(),
        ]);
        const totalTokenCost = tu.reduce((total: number, item: any) => total + Number(item.cost ?? 0), 0);
        setSummary({ ...sum, total_token_cost: totalTokenCost });
        setRunsOverTime(rot);
        setAnomaliesBySeverity(abs);
        setAgentsPerf(ap);
        setTokenUsage(tu);
        setPipelineHealth(ph);
        setAnomaliesTrend(at);
        setTopAnomalyTypes(tat);
        setRunStatusDist(rsd);
        setRecentAlerts(ra);
        setLocked(false);
      } catch (err: any) {
        if (err?.status === 403 || err?.message?.includes('403')) {
          setLocked(true);
          setLockReason(err?.detail || 'Dashboard is locked until a run is approved via HITL Review.');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [run_id]);

  const sevColor: Record<string, string> = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-yellow-400',
    low: 'text-blue-400',
  };

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <LoadingSpinner size="lg" />
    </div>
  );

  if (locked) return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mx-auto mb-5">
          <Lock size={36} className="text-slate-500" />
        </div>
        <h2 className="text-xl font-bold text-white font-space mb-2">Dashboard Locked</h2>
        <p className="text-slate-400 text-sm mb-6">{lockReason || 'Complete the pipeline run and approve it via HITL Review to unlock the dashboard.'}</p>
        <button
          onClick={() => navigate('/review')}
          className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
        >
          Go to Review →
        </button>
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-space flex items-center gap-2">
            <BarChart2 size={22} className="text-blue-400" /> Analytics Dashboard
          </h1>
          <p className="text-sm text-slate-400 font-dm mt-1">
            {summary?.approved_run_id ? (
              <>Based on approved run: <span className="text-slate-300 font-mono text-xs">{summary.approved_run_id}</span></>
            ) : 'Aggregate analytics across all approved pipeline runs'}
          </p>
        </div>
        {summary?.last_updated && (
          <div className="text-xs text-slate-500 flex items-center gap-1">
            <Clock size={12} /> Updated {formatDateTime(summary.last_updated)}
          </div>
        )}
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Pipeline Runs"
          value={summary?.total_runs ?? '—'}
          icon={<Activity size={18} className="text-blue-400" />}
        />
        <KpiCard
          label="Anomalies Detected"
          value={summary?.total_anomalies ?? '—'}
          icon={<AlertTriangle size={18} className="text-orange-400" />}
        />
        <KpiCard
          label="Avg Confidence Score"
          value={summary?.avg_confidence_score ? `${summary.avg_confidence_score}%` : '—'}
          icon={<CheckCircle size={18} className="text-green-400" />}
        />
        <KpiCard
          label="Total Token Cost"
          value={summary?.total_token_cost ? `$${summary.total_token_cost.toFixed(2)}` : '—'}
          icon={<DollarSign size={18} className="text-purple-400" />}
        />
      </div>

      {/* AI Pillars */}
      {summary?.pillar_scores && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 font-space flex items-center gap-2 mb-3">
            <Cpu size={15} className="text-blue-400" /> AI Monitoring Pillars
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {PILLAR_DEFS.map(p => {
              const score = summary.pillar_scores[p.key];
              return (
                <PillarCard
                  key={p.key}
                  label={p.label}
                  icon={p.icon}
                  score={score?.score ?? 0}
                  color={p.color}
                  findings={score?.findings ?? 0}
                  status={score?.status ?? 'normal'}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <TrendingUp size={15} className="text-blue-400" /> Pipeline Runs Over Time
          </h3>
          <PipelineRunsChart data={runsOverTime} />
        </GlassCard>
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <Activity size={15} className="text-orange-400" /> Anomalies Trend
          </h3>
          <AnomaliesTrendChart data={anomaliesTrend} />
        </GlassCard>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <AlertTriangle size={15} className="text-red-400" /> Anomalies by Severity
          </h3>
          <SeverityPieChart data={anomaliesBySeverity} />
        </GlassCard>
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <CheckCircle size={15} className="text-green-400" /> Run Status Distribution
          </h3>
          <RunStatusPieChart data={runStatusDist} />
        </GlassCard>
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <DollarSign size={15} className="text-purple-400" /> Token Cost by Run
          </h3>
          <TokenCostChart data={tokenUsage} />
        </GlassCard>
      </div>

      {/* Agent Performance + Top Anomaly Types */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <Cpu size={15} className="text-blue-400" /> Agent Performance
          </h3>
          <div className="space-y-3">
            {agentsPerf.map((ag, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-28 text-xs text-slate-400 truncate">{ag.name}</div>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${ag.confidence}%`,
                      background: ag.confidence >= 80 ? '#10B981' : ag.confidence >= 60 ? '#F59E0B' : '#EF4444',
                    }}
                  />
                </div>
                <div className="w-10 text-right text-xs font-mono font-medium text-white">{ag.confidence}%</div>
                <div className="w-12 text-right text-xs text-slate-500">{ag.inferences} inf.</div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
            <BarChart2 size={15} className="text-orange-400" /> Top Anomaly Types
          </h3>
          <div className="space-y-2.5">
            {topAnomalyTypes.map((t, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-6 text-xs text-slate-600 font-mono">#{i + 1}</div>
                <div className="flex-1 text-xs text-slate-300 truncate">{t.type}</div>
                <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500/60 rounded-full"
                    style={{ width: `${(t.count / (topAnomalyTypes[0]?.count || 1)) * 100}%` }}
                  />
                </div>
                <div className="w-8 text-right text-xs font-mono text-slate-300">{t.count}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Pipeline Health + Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {pipelineHealth && (
          <GlassCard className="p-4">
            <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-4">
              <Activity size={15} className="text-green-400" /> Pipeline Health Metrics
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(pipelineHealth).filter(([k]) => k !== 'overall').map(([key, val]: any) => (
                <div key={key} className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                  <div className="text-xs text-slate-500 capitalize mb-1">{key.replace(/_/g, ' ')}</div>
                  <div className={`text-sm font-bold font-space ${
                    typeof val === 'number'
                      ? val >= 95 ? 'text-green-400' : val >= 80 ? 'text-yellow-400' : 'text-red-400'
                      : 'text-white'
                  }`}>
                    {typeof val === 'number' ? `${val}%` : val}
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        <GlassCard className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2">
              <AlertTriangle size={15} className="text-red-400" /> Recent Alerts
            </h3>
            <button onClick={() => navigate('/alerts')} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              View all <ChevronRight size={12} />
            </button>
          </div>
          <div className="space-y-2">
            {recentAlerts.length === 0 ? (
              <div className="text-center py-6 text-slate-500 text-sm">No recent alerts</div>
            ) : recentAlerts.map((a, i) => (
              <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/40 hover:bg-slate-800/60 transition-colors">
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                  a.severity === 'critical' ? 'bg-red-500' :
                  a.severity === 'high' ? 'bg-orange-500' :
                  a.severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-slate-200 truncate">{a.title}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[10px] ${sevColor[a.severity] || 'text-slate-400'}`}>{a.severity}</span>
                    <span className="text-[10px] text-slate-600">{formatDateTime(a.triggered_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
