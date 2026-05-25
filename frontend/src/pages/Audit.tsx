import { useState, useEffect, useCallback } from 'react';
import { Shield, Download, Search, Filter, ChevronRight, Clock, Eye, FileText, Lock, X, Calendar } from 'lucide-react';
import { auditApi } from '../lib/api';
import { AuditEvent } from '../lib/types';
import { GlassCard, LoadingSpinner, Modal } from '../components/ui';
import { formatDateTime } from '../lib/utils';

const EVENT_TYPE_COLORS: Record<string, string> = {
  pipeline_started: 'text-blue-400 bg-blue-500/10',
  pipeline_completed: 'text-green-400 bg-green-500/10',
  pipeline_failed: 'text-red-400 bg-red-500/10',
  run_approved: 'text-green-400 bg-green-500/10',
  run_rejected: 'text-red-400 bg-red-500/10',
  alert_triggered: 'text-orange-400 bg-orange-500/10',
  alert_acknowledged: 'text-yellow-400 bg-yellow-500/10',
  alert_escalated: 'text-purple-400 bg-purple-500/10',
  user_login: 'text-blue-400 bg-blue-500/10',
  user_logout: 'text-slate-400 bg-slate-500/10',
  prompt_sent: 'text-cyan-400 bg-cyan-500/10',
  data_uploaded: 'text-teal-400 bg-teal-500/10',
  config_changed: 'text-yellow-400 bg-yellow-500/10',
};

const EVENT_ICONS: Record<string, string> = {
  pipeline_started: '▶',
  pipeline_completed: '✓',
  pipeline_failed: '✗',
  run_approved: '✅',
  run_rejected: '❌',
  alert_triggered: '⚠',
  alert_acknowledged: '👁',
  alert_escalated: '⬆',
  user_login: '→',
  user_logout: '←',
  prompt_sent: '💬',
  data_uploaded: '📤',
  config_changed: '⚙',
};

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [promptModal, setPromptModal] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [filterUser, setFilterUser] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const fetchEvents = useCallback(async () => {
    try {
      setLoading(true);
      const [ev, sum] = await Promise.all([
        auditApi.getEvents({
          event_type: filterType !== 'all' ? filterType : undefined,
          user: filterUser !== 'all' ? filterUser : undefined,
          from_date: dateFrom || undefined,
          to_date: dateTo || undefined,
        }),
        auditApi.getSummary(),
      ]);
      setEvents(ev);
      setSummary(sum);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [filterType, filterUser, dateFrom, dateTo]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const blob = await auditApi.export(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_log_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { console.error('Export failed', e); }
  };

  const handleViewPrompt = async (eventId: string) => {
    try {
      const prompt = await auditApi.getPrompt(eventId);
      setPromptModal(prompt);
    } catch (e) { console.error(e); }
  };

  const filtered = events.filter(e => {
    if (!search) return true;
    return (
      e.event_type.toLowerCase().includes(search.toLowerCase()) ||
      e.user?.toLowerCase().includes(search.toLowerCase()) ||
      e.details?.toLowerCase().includes(search.toLowerCase()) ||
      e.run_id?.toLowerCase().includes(search.toLowerCase())
    );
  });

  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const uniqueTypes = Array.from(new Set(events.map(e => e.event_type)));
  const uniqueUsers = Array.from(new Set(events.map(e => e.user).filter(Boolean)));

  return (
    <div className="p-6 space-y-5 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-space flex items-center gap-2">
            <Shield size={22} className="text-blue-400" /> Audit Log
          </h1>
          <p className="text-sm text-slate-400 mt-1 font-dm flex items-center gap-1">
            <Lock size={12} /> Immutable event trail — all actions are cryptographically recorded
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs transition-colors"
          >
            <Download size={13} /> Export CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs transition-colors"
          >
            <Download size={13} /> Export JSON
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Total Events', value: summary.total_events, color: 'text-blue-400' },
            { label: 'Pipeline Events', value: summary.pipeline_events, color: 'text-green-400' },
            { label: 'Alert Events', value: summary.alert_events, color: 'text-orange-400' },
            { label: 'Prompt Events', value: summary.prompt_events, color: 'text-purple-400' },
          ].map((s, i) => (
            <GlassCard key={i} className="p-3">
              <div className="text-xs text-slate-500 mb-1">{s.label}</div>
              <div className={`text-xl font-bold font-space ${s.color}`}>{s.value?.toLocaleString() ?? '—'}</div>
            </GlassCard>
          ))}
        </div>
      )}

      {/* Filters */}
      <GlassCard className="p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Search events, users, run IDs..."
              className="w-full bg-slate-800/50 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filterType}
            onChange={e => { setFilterType(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Types</option>
            {uniqueTypes.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
          </select>

          <select
            value={filterUser}
            onChange={e => { setFilterUser(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Users</option>
            {uniqueUsers.map(u => <option key={u} value={u}>{u}</option>)}
          </select>

          <div className="flex items-center gap-1.5">
            <Calendar size={13} className="text-slate-500" />
            <input
              type="date"
              value={dateFrom}
              onChange={e => { setDateFrom(e.target.value); setPage(1); }}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
            />
            <span className="text-slate-500 text-xs">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={e => { setDateTo(e.target.value); setPage(1); }}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
            />
            {(dateFrom || dateTo) && (
              <button onClick={() => { setDateFrom(''); setDateTo(''); }} className="text-slate-500 hover:text-slate-300 transition-colors">
                <X size={13} />
              </button>
            )}
          </div>
        </div>
      </GlassCard>

      {/* Event Table */}
      <GlassCard className="overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-800 text-left">
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Timestamp</th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Event</th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Run ID</th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Details</th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {paginated.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-slate-500 text-sm">
                        No audit events match your filters
                      </td>
                    </tr>
                  ) : paginated.map((ev, i) => {
                    const typeColor = EVENT_TYPE_COLORS[ev.event_type] || 'text-slate-400 bg-slate-500/10';
                    const icon = EVENT_ICONS[ev.event_type] || '•';
                    return (
                      <tr
                        key={(ev as any).row_key ?? ev.id}
                        className="hover:bg-slate-800/20 transition-colors cursor-pointer"
                        onClick={() => setSelected(ev)}
                      >
                        <td className="px-4 py-2.5">
                          <span className="text-xs font-mono text-slate-400 flex items-center gap-1 whitespace-nowrap">
                            <Clock size={10} /> {formatDateTime(ev.timestamp)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${typeColor}`}>
                            <span>{icon}</span>
                            <span className="capitalize">{ev.event_type.replace(/_/g, ' ')}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs text-slate-300">{ev.user || '—'}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs font-mono text-blue-300">{ev.run_id || '—'}</span>
                        </td>
                        <td className="px-4 py-2.5 max-w-xs">
                          <span className="text-xs text-slate-400 truncate block">{ev.details || '—'}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={e => { e.stopPropagation(); setSelected(ev); }}
                              className="text-slate-500 hover:text-slate-300 transition-colors"
                              title="View details"
                            >
                              <Eye size={13} />
                            </button>
                            {ev.has_prompt && (
                              <button
                                onClick={e => { e.stopPropagation(); handleViewPrompt(ev.id); }}
                                className="text-slate-500 hover:text-blue-400 transition-colors"
                                title="View prompt"
                              >
                                <FileText size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800">
                <span className="text-xs text-slate-500">
                  {filtered.length} events · Page {page} of {totalPages}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                    className="px-2.5 py-1 rounded text-xs border border-slate-700 text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Prev
                  </button>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
                    return (
                      <button
                        key={p}
                        onClick={() => setPage(p)}
                        className={`w-7 h-7 rounded text-xs transition-colors ${
                          page === p ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        {p}
                      </button>
                    );
                  })}
                  <button
                    disabled={page === totalPages}
                    onClick={() => setPage(p => p + 1)}
                    className="px-2.5 py-1 rounded text-xs border border-slate-700 text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </GlassCard>

      {/* Event Detail Modal */}
      <Modal open={!!selected} onClose={() => setSelected(null)} title="Audit Event Detail">
        {selected && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full ${EVENT_TYPE_COLORS[selected.event_type] || 'text-slate-400 bg-slate-500/10'}`}>
                {EVENT_ICONS[selected.event_type]} {selected.event_type.replace(/_/g, ' ')}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">Event ID</div>
                <code className="text-xs text-blue-300 font-mono">{selected.id}</code>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Timestamp</div>
                <div className="text-sm text-slate-300">{formatDateTime(selected.timestamp)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">User</div>
                <div className="text-sm text-slate-300">{selected.user || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">IP Address</div>
                <code className="text-xs text-slate-300 font-mono">{selected.ip_address || '—'}</code>
              </div>
            </div>

            {selected.run_id && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Run ID</div>
                <code className="text-sm text-blue-300 font-mono">{selected.run_id}</code>
              </div>
            )}

            {selected.details && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Details</div>
                <p className="text-sm text-slate-300">{selected.details}</p>
              </div>
            )}

            {selected.metadata && Object.keys(selected.metadata).length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Metadata</div>
                <div className="bg-slate-900/60 rounded-lg p-3 font-mono text-xs text-slate-300 overflow-auto max-h-40">
                  {JSON.stringify(selected.metadata, null, 2)}
                </div>
              </div>
            )}

            {selected.hash && (
              <div>
                <div className="text-xs text-slate-500 mb-1 flex items-center gap-1">
                  <Lock size={10} /> Integrity Hash
                </div>
                <code className="text-xs text-green-400 font-mono break-all">{selected.hash}</code>
              </div>
            )}

            {selected.has_prompt && (
              <button
                onClick={() => handleViewPrompt(selected.id)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20 text-sm transition-colors"
              >
                <FileText size={14} /> View AI Prompt
              </button>
            )}
          </div>
        )}
      </Modal>

      {/* Prompt Modal */}
      <Modal open={!!promptModal} onClose={() => setPromptModal(null)} title="AI Prompt Trace">
        {promptModal && (
          <div className="space-y-4">
            <div>
              <div className="text-xs text-slate-500 mb-1">Agent</div>
              <div className="text-sm text-slate-300">{promptModal.agent}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">System Prompt</div>
              <pre className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-lg overflow-auto max-h-32 whitespace-pre-wrap">{promptModal.system_prompt}</pre>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">User Prompt</div>
              <pre className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-lg overflow-auto max-h-32 whitespace-pre-wrap">{promptModal.user_prompt}</pre>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Response</div>
              <pre className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-lg overflow-auto max-h-32 whitespace-pre-wrap">{promptModal.response}</pre>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">Model</div>
                <div className="text-xs text-slate-300 font-mono">{promptModal.model}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Tokens</div>
                <div className="text-xs text-slate-300 font-mono">{promptModal.tokens?.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Latency</div>
                <div className="text-xs text-slate-300 font-mono">{promptModal.latency_ms}ms</div>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
