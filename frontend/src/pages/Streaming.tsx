import { useState, useEffect, useCallback } from 'react';
import { Activity, Cpu, Zap, Clock, AlertTriangle, CheckCircle, RefreshCw, Eye, TrendingUp, Database, Radio, Layers } from 'lucide-react';
import { pipelineApi, streamingApi } from '../lib/api';
import { StreamingStatus, StreamingEvent, AgentStatus, AIFinding } from '../lib/types';
import { ConsumerLagChart, ThroughputChart } from '../components/charts';
import { GlassCard, StatusBadge, AgentCard, LoadingSpinner, ConfidenceBadge } from '../components/ui';
import { formatDateTime, agentLabel, agentColor, AGENT_NAMES } from '../lib/utils';

export default function Streaming() {
  const [status, setStatus] = useState<StreamingStatus | null>(null);
  const [lagHistory, setLagHistory] = useState<{ time: string; lag: number }[]>([]);
  const [throughputHistory, setThroughputHistory] = useState<{ time: string; in: number; out: number }[]>([]);
  const [events, setEvents] = useState<StreamingEvent[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [findings, setFindings] = useState<AIFinding[]>([]);
  const [windowStatus, setWindowStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [activeTab, setActiveTab] = useState<'events' | 'findings'>('events');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [runId, setRunId] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const activeRun = await pipelineApi.getActiveRun().catch(() => null);
      const currentRunId = activeRun?.run_id ?? runId;

      if (activeRun?.run_id && activeRun.run_id !== runId) {
        setRunId(activeRun.run_id);
      }

      const kafkaHealthPromise = pipelineApi.kafkaHealth().catch(() => null);

      if (!currentRunId) {
        const kafkaHealth = await kafkaHealthPromise;
        setStatus({
          run_id: '',
          pipeline_status: activeRun?.status ?? 'idle',
          kafka_connected: Boolean(kafkaHealth?.kafka_available),
          records_processed: 0,
          throughput_per_sec: 0,
          consumer_lag: 0,
          anomalies_detected: 0,
          partitions: 0,
          uptime: '0s',
        });
        setLagHistory([]);
        setThroughputHistory([]);
        setEvents([]);
        setAgents([]);
        setFindings([]);
        setWindowStatus(null);
        setLastRefresh(new Date());
        return;
      }

      const [s, lag, tp, ev, ag, fi, ws, kafkaHealth] = await Promise.all([
        streamingApi.getStatus(currentRunId).catch((error) => ({ error })),
        streamingApi.getLagHistory(currentRunId).catch((error) => ({ error })),
        streamingApi.getThroughputHistory(currentRunId).catch((error) => ({ error })),
        streamingApi.getRecentEvents(currentRunId).catch((error) => ({ error })),
        streamingApi.getAgentsStatus(currentRunId).catch((error) => ({ error })),
        streamingApi.getAIFindings(currentRunId).catch((error) => ({ error })),
        streamingApi.getWindowStatus(currentRunId).catch((error) => ({ error })),
        kafkaHealthPromise,
      ]);

      const statusData = (s as any)?.error ? null : s;
      const lagResponse = (lag as any)?.error ? [] : lag;
      const throughputResponse = (tp as any)?.error ? [] : tp;
      const eventsResponse = (ev as any)?.error ? [] : ev;
      const agentsResponse = (ag as any)?.error ? [] : ag;
      const findingsResponse = (fi as any)?.error ? [] : fi;
      const windowResponse = (ws as any)?.error ? null : ws;

      const lagData = Array.isArray(lagResponse)
        ? lagResponse
        : (lagResponse?.data_points ?? []).map((point: any) => ({
            time: point.timestamp ?? '',
            lag: Number(point.consumer_lag ?? 0),
          }));

      const tpData = Array.isArray(throughputResponse)
        ? throughputResponse
        : (throughputResponse?.data_points ?? []).map((point: any) => ({
            time: point.timestamp ?? '',
            in: Number(point.events_per_sec ?? 0),
            out: Number(point.events_per_sec ?? 0),
          }));

      const eventsData = Array.isArray(eventsResponse)
        ? eventsResponse
        : (eventsResponse?.events ?? []).map((item: any) => ({
            event_type: item.event_type ?? 'record_processed',
            message: item.message ?? item.status ?? 'Event received',
            severity: item.severity ?? null,
            agent: item.agent ?? null,
            record_id: item.record_id ?? item.event_id ?? null,
            timestamp: item.time ?? item.timestamp ?? new Date().toISOString(),
          }));

      const agentsData = Array.isArray(agentsResponse)
        ? agentsResponse
        : (agentsResponse?.agents ?? []).map((item: any, index: number) => ({
            agent_id: item.name ?? `agent-${index}`,
            name: item.name ?? `Agent ${index + 1}`,
            status: item.status ?? 'PENDING',
            last_run: item.last_run ?? '',
            confidence: typeof item.confidence === 'number' ? item.confidence : 0,
            inferences: item.findings ? 1 : 0,
            findings_count: item.findings ? 1 : 0,
            avg_latency_ms: 0,
          }));

      const findingsData = Array.isArray(findingsResponse)
        ? findingsResponse
        : (findingsResponse?.findings ?? []).map((item: any) => ({
            finding_type: item.finding_type ?? item.message ?? 'Finding',
            severity: item.severity ?? 'low',
            confidence: typeof item.confidence === 'number' ? item.confidence : 0,
            description: item.description ?? item.message ?? '',
            agent: item.agent ?? 'pipeline',
            record_ids: Array.isArray(item.record_ids) ? item.record_ids : (item.id ? [item.id] : []),
            affected_field: item.affected_field ?? null,
            recommendation: item.recommendation ?? '',
          }));

      const normalizedWindow = windowResponse
        ? {
            window_size_seconds: windowResponse.window_size ?? windowResponse.window_size_seconds ?? 0,
            current_window: windowResponse.current_window ?? 1,
            windows_closed: windowResponse.window_end ? 1 : 0,
            next_close_in: windowResponse.window_end
              ? Math.max(0, Math.ceil((new Date(windowResponse.window_end).getTime() - Date.now()) / 1000))
              : 0,
          }
        : null;

      setStatus(statusData ? {
        ...statusData,
        kafka_connected: Boolean(kafkaHealth?.kafka_available),
        records_processed: statusData.records_processed ?? statusData.events_processed ?? 0,
        throughput_per_sec: statusData.throughput_per_sec ?? statusData.events_per_sec_avg ?? 0,
        consumer_lag: statusData.consumer_lag ?? statusData.consumer?.consumer_lag_avg ?? 0,
        partitions: statusData.partitions ?? statusData.topic?.partitions ?? 0,
        uptime: statusData.uptime ?? `${Math.floor((statusData.uptime_seconds ?? 0) / 60)}m`,
      } : {
        run_id: currentRunId,
        pipeline_status: activeRun?.status ?? 'unknown',
        kafka_connected: Boolean(kafkaHealth?.kafka_available),
      });
      setLagHistory(lagData);
      setThroughputHistory(tpData);
      setEvents(eventsData);
      setAgents(agentsData);
      setFindings(findingsData);
      setWindowStatus(normalizedWindow);
      setLastRefresh(new Date());
    } catch (e) {
      console.error('Streaming fetch error', e);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 3000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const filteredFindings = filterSeverity === 'all'
    ? findings
    : findings.filter(f => f.severity === filterSeverity);

  const severityColor: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  };

  const eventTypeIcon: Record<string, JSX.Element> = {
    anomaly_detected: <AlertTriangle size={13} className="text-red-400" />,
    record_processed: <CheckCircle size={13} className="text-green-400" />,
    agent_inference: <Cpu size={13} className="text-blue-400" />,
    window_closed: <Clock size={13} className="text-purple-400" />,
    lag_spike: <TrendingUp size={13} className="text-orange-400" />,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Radio size={20} className="text-blue-400 animate-pulse" />
            <h1 className="text-2xl font-bold text-white font-space">Live Streaming Monitor</h1>
          </div>
          <p className="text-sm text-slate-400 font-dm">
            Run: <span className="text-slate-200 font-mono text-xs">{runId ?? 'No active run'}</span>
            &nbsp;·&nbsp;Refreshes every 3s
            &nbsp;·&nbsp;Last: <span className="text-slate-300">{lastRefresh.toLocaleTimeString()}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${
            status?.kafka_connected ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${status?.kafka_connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            Kafka {status?.kafka_connected ? 'Connected' : 'Disconnected'}
          </div>
          <button onClick={fetchAll} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs transition-colors">
            <RefreshCw size={13} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          { label: 'Records/sec', value: status?.throughput_per_sec?.toLocaleString() ?? '—', icon: <Zap size={16} className="text-blue-400" />, sub: 'throughput' },
          { label: 'Consumer Lag', value: status?.consumer_lag?.toLocaleString() ?? '—', icon: <TrendingUp size={16} className="text-orange-400" />, sub: 'messages behind' },
          { label: 'Processed', value: status?.records_processed?.toLocaleString() ?? '—', icon: <Database size={16} className="text-green-400" />, sub: 'total records' },
          { label: 'Anomalies', value: status?.anomalies_detected?.toString() ?? '—', icon: <AlertTriangle size={16} className="text-red-400" />, sub: 'detected' },
          { label: 'Partitions', value: status?.partitions?.toString() ?? '—', icon: <Layers size={16} className="text-purple-400" />, sub: 'active' },
          { label: 'Uptime', value: status?.uptime ?? '—', icon: <Activity size={16} className="text-teal-400" />, sub: 'stream runtime' },
        ].map((k, i) => (
          <GlassCard key={i} className="p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500 font-dm">{k.label}</span>
              {k.icon}
            </div>
            <div className="text-xl font-bold text-white font-space">{k.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{k.sub}</div>
          </GlassCard>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2">
              <TrendingUp size={15} className="text-orange-400" /> Consumer Lag (60s)
            </h3>
            <span className="text-xs text-slate-500">Live · 3s interval</span>
          </div>
          <ConsumerLagChart data={lagHistory} />
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2">
              <Activity size={15} className="text-blue-400" /> Throughput In / Out
            </h3>
            <span className="text-xs text-slate-500">Records/sec</span>
          </div>
          <ThroughputChart data={throughputHistory} />
        </GlassCard>
      </div>

      {/* Window Status */}
      {windowStatus && (
        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-3">
            <Clock size={15} className="text-purple-400" /> Tumbling Window Status
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-slate-500 mb-1">Window Size</div>
              <div className="text-sm font-medium text-white font-mono">{windowStatus.window_size_seconds}s</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Current Window</div>
              <div className="text-sm font-medium text-white font-mono">#{windowStatus.current_window}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Windows Closed</div>
              <div className="text-sm font-medium text-white font-mono">{windowStatus.windows_closed}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Next Close In</div>
              <div className="text-sm font-medium text-blue-400 font-mono">{windowStatus.next_close_in}s</div>
            </div>
          </div>
          {/* Progress bar for current window */}
          <div className="mt-3">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Window progress</span>
              <span>{Math.round(((windowStatus.window_size_seconds - windowStatus.next_close_in) / windowStatus.window_size_seconds) * 100)}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-1000"
                style={{ width: `${((windowStatus.window_size_seconds - windowStatus.next_close_in) / windowStatus.window_size_seconds) * 100}%` }}
              />
            </div>
          </div>
        </GlassCard>
      )}

      {/* Agents Grid */}
      <div>
        <h3 className="text-sm font-semibold text-slate-300 font-space flex items-center gap-2 mb-3">
          <Cpu size={15} className="text-blue-400" /> AI Agent Status
          <span className="text-xs text-slate-500 font-normal">({agents.length} agents active)</span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {agents.map(agent => (
            <AgentCard key={agent.agent_id} agent={agent} />
          ))}
        </div>
      </div>

      {/* Events + Findings Tabs */}
      <GlassCard>
        <div className="border-b border-slate-800 px-4">
          <div className="flex items-center gap-0">
            {(['events', 'findings'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                }`}
              >
                {tab === 'events' ? `Stream Events (${events.length})` : `AI Findings (${findings.length})`}
              </button>
            ))}
            {activeTab === 'findings' && (
              <div className="ml-auto flex items-center gap-2 py-2 pr-1">
                <span className="text-xs text-slate-500">Filter:</span>
                {['all', 'critical', 'high', 'medium', 'low'].map(sev => (
                  <button
                    key={sev}
                    onClick={() => setFilterSeverity(sev)}
                    className={`px-2 py-0.5 rounded text-xs capitalize transition-colors ${
                      filterSeverity === sev ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {activeTab === 'events' && (
          <div className="divide-y divide-slate-800/50 max-h-80 overflow-y-auto">
            {events.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">No events yet</div>
            ) : events.map((ev, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-2.5 hover:bg-slate-800/30 transition-colors">
                <div className="mt-0.5">{eventTypeIcon[ev.event_type] ?? <Activity size={13} className="text-slate-500" />}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-200 truncate">{ev.message}</span>
                    {ev.severity && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${severityColor[ev.severity] ?? ''}`}>
                        {ev.severity}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-[10px] text-slate-500 font-mono">{ev.event_type}</span>
                    {ev.agent && <span className="text-[10px] text-slate-500">· {agentLabel(ev.agent)}</span>}
                    {ev.record_id && <span className="text-[10px] text-slate-500 font-mono">· {ev.record_id}</span>}
                  </div>
                </div>
                <span className="text-[10px] text-slate-600 font-mono shrink-0">{formatDateTime(ev.timestamp)}</span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'findings' && (
          <div className="divide-y divide-slate-800/50 max-h-80 overflow-y-auto">
            {filteredFindings.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">No findings match this filter</div>
            ) : filteredFindings.map((f, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-800/30 transition-colors">
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                  f.severity === 'critical' ? 'bg-red-500' :
                  f.severity === 'high' ? 'bg-orange-500' :
                  f.severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-medium text-slate-200">{f.finding_type}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${severityColor[f.severity]}`}>{f.severity}</span>
                    <ConfidenceBadge score={f.confidence} />
                  </div>
                  <p className="text-xs text-slate-400">{f.description}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-[10px] text-slate-500">Agent: {agentLabel(f.agent)}</span>
                    {f.record_ids?.length > 0 && (
                      <span className="text-[10px] text-slate-500">Records: {f.record_ids.join(', ')}</span>
                    )}
                  </div>
                </div>
                <Eye size={13} className="text-slate-600 mt-0.5 shrink-0" />
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
