import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, XCircle, ChevronRight, AlertTriangle, FileText, Download, Eye, ThumbsUp, ThumbsDown, Clock, Cpu, BarChart2, Info } from 'lucide-react';
import { reviewApi } from '../lib/api';
import { ReviewFinding, TokenUsage } from '../lib/types';
import { GlassCard, ConfidenceBadge, LoadingSpinner, Modal, StatusBadge } from '../components/ui';
import { agentLabel, formatDateTime, AGENT_NAMES } from '../lib/utils';

const AGENT_TABS = [
  { id: 'data_quality', label: 'Data Quality', color: 'blue' },
  { id: 'log_analysis', label: 'Log Analysis', color: 'purple' },
  { id: 'rca', label: 'Root Cause', color: 'orange' },
  { id: 'recommendation', label: 'Recommendations', color: 'green' },
  { id: 'compliance', label: 'Compliance', color: 'red' },
];

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

export default function Review() {
  const [pending, setPending] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<string>('');
  const [findings, setFindings] = useState<ReviewFinding[]>([]);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [activeAgent, setActiveAgent] = useState<string>('data_quality');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<ReviewFinding | null>(null);
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | null>(null);
  const [decisionNote, setDecisionNote] = useState('');
  const [toastMsg, setToastMsg] = useState<string>('');

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3500);
  };

  const fetchPending = useCallback(async () => {
    try {
      const p = await reviewApi.getPending();
      setPending(p);
      if (p.length > 0 && !selectedRun) {
        setSelectedRun(p[0].run_id);
      }
    } catch (e) { console.error(e); }
  }, [selectedRun]);

  useEffect(() => { fetchPending(); }, []);

  useEffect(() => {
    if (!selectedRun) return;
    setLoading(true);
    Promise.all([
      reviewApi.getFindings(selectedRun),
      reviewApi.getTokenUsage(selectedRun),
      reviewApi.getArtifacts(selectedRun),
    ]).then(([f, t, a]) => {
      setFindings(f);
      setTokenUsage(t);
      setArtifacts(a);
    }).catch(console.error).finally(() => setLoading(false));
  }, [selectedRun]);

  const agentFindings = findings.filter(f => f.agent === activeAgent);
  const sortedFindings = [...agentFindings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  const agentSummary = (agentId: string) => {
    const aFindings = findings.filter(f => f.agent === agentId);
    const critical = aFindings.filter(f => f.severity === 'critical').length;
    const high = aFindings.filter(f => f.severity === 'high').length;
    const avgConf = aFindings.length ? Math.round(aFindings.reduce((s, f) => s + f.confidence, 0) / aFindings.length) : 0;
    return { count: aFindings.length, critical, high, avgConf };
  };

  const handleDecision = async () => {
    if (!decisionModal || !selectedRun) return;
    setSubmitting(true);
    try {
      if (decisionModal === 'approve') {
        await reviewApi.approve({ run_id: selectedRun, notes: decisionNote });
        showToast('✓ Run approved successfully — Dashboard is now unlocked.');
      } else {
        await reviewApi.reject({ run_id: selectedRun, reason: decisionNote });
        showToast('✗ Run rejected. A new pipeline run will be required.');
      }
      setDecisionModal(null);
      setDecisionNote('');
      fetchPending();
    } catch (e) {
      showToast('Error submitting decision. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const sevColor: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    info: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
  };

  const activeAgentMeta = AGENT_TABS.find(a => a.id === activeAgent)!;

  return (
    <div className="p-6 space-y-5 max-w-[1600px] mx-auto">
      {/* Toast */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-800 border border-slate-700 text-white px-4 py-3 rounded-xl shadow-xl text-sm max-w-sm animate-fade-in">
          {toastMsg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-space flex items-center gap-2">
            <Eye size={22} className="text-blue-400" /> Human-in-the-Loop Review
          </h1>
          <p className="text-sm text-slate-400 font-dm mt-1">
            Review AI agent findings and approve or reject the pipeline run before Dashboard access is granted.
          </p>
        </div>
        {selectedRun && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setDecisionModal('reject'); setDecisionNote(''); }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 text-sm transition-colors"
            >
              <ThumbsDown size={14} /> Reject Run
            </button>
            <button
              onClick={() => { setDecisionModal('approve'); setDecisionNote(''); }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20 text-sm transition-colors"
            >
              <ThumbsUp size={14} /> Approve Run
            </button>
          </div>
        )}
      </div>

      {/* Pending Runs Selector */}
      {pending.length > 0 && (
        <GlassCard className="p-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs text-slate-500 shrink-0">Pending Review:</span>
            {pending.map(r => (
              <button
                key={r.run_id}
                onClick={() => setSelectedRun(r.run_id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                  selectedRun === r.run_id
                    ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                    : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Clock size={11} />
                {r.run_id}
                <span className="text-[10px] opacity-60">{r.records_processed?.toLocaleString()} records</span>
              </button>
            ))}
          </div>
        </GlassCard>
      )}

      {pending.length === 0 && !loading && (
        <GlassCard className="p-8 text-center">
          <CheckCircle size={40} className="text-green-400 mx-auto mb-3 opacity-60" />
          <p className="text-slate-300 font-medium">No runs pending review</p>
          <p className="text-slate-500 text-sm mt-1">All pipeline runs have been reviewed. Start a new pipeline run to generate findings.</p>
        </GlassCard>
      )}

      {loading && selectedRun && (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {!loading && selectedRun && (
        <>
          {/* Compliance alert banner */}
          {findings.filter(f => f.agent === 'compliance' && (f.severity === 'critical' || f.severity === 'high')).length > 0 && (
            <div className="flex items-start gap-3 p-3 rounded-xl bg-red-500/10 border border-red-500/30">
              <AlertTriangle size={16} className="text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-300">Compliance Issues Detected</p>
                <p className="text-xs text-red-400/80 mt-0.5">
                  {findings.filter(f => f.agent === 'compliance' && (f.severity === 'critical' || f.severity === 'high')).length} critical/high compliance findings require attention before approval.
                </p>
              </div>
            </div>
          )}

          {/* Token Usage + Summary Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <GlassCard className="p-4 lg:col-span-2">
              <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-3">
                <Cpu size={15} className="text-blue-400" /> Agent Findings Summary
              </h3>
              <div className="grid grid-cols-5 gap-2">
                {AGENT_TABS.map(tab => {
                  const s = agentSummary(tab.id);
                  return (
                    <div
                      key={tab.id}
                      onClick={() => setActiveAgent(tab.id)}
                      className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                        activeAgent === tab.id ? 'bg-blue-600/20 border-blue-500/40' : 'bg-slate-800/50 border-slate-700/50 hover:border-slate-600'
                      }`}
                    >
                      <div className="text-xs font-medium text-slate-300 mb-1 truncate">{tab.label}</div>
                      <div className="text-lg font-bold text-white font-space">{s.count}</div>
                      <div className="flex items-center gap-1 mt-1">
                        {s.critical > 0 && <span className="text-[10px] px-1 py-0.5 rounded bg-red-500/20 text-red-400">{s.critical}C</span>}
                        {s.high > 0 && <span className="text-[10px] px-1 py-0.5 rounded bg-orange-500/20 text-orange-400">{s.high}H</span>}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">Avg conf: {s.avgConf}%</div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>

            {tokenUsage && (
              <GlassCard className="p-4">
                <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-3">
                  <BarChart2 size={15} className="text-purple-400" /> Token Usage
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Input tokens</span>
                    <span className="text-white font-mono">{tokenUsage.input_tokens?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Output tokens</span>
                    <span className="text-white font-mono">{tokenUsage.output_tokens?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm border-t border-slate-700 pt-2">
                    <span className="text-slate-400">Total tokens</span>
                    <span className="text-white font-bold font-mono">{tokenUsage.total_tokens?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Est. cost</span>
                    <span className="text-green-400 font-bold">${tokenUsage.estimated_cost?.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Model</span>
                    <span className="text-slate-300 text-xs">{tokenUsage.model}</span>
                  </div>
                </div>
              </GlassCard>
            )}
          </div>

          {/* Agent Tab + Findings */}
          <GlassCard>
            <div className="border-b border-slate-800">
              <div className="flex overflow-x-auto">
                {AGENT_TABS.map(tab => {
                  const s = agentSummary(tab.id);
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveAgent(tab.id)}
                      className={`px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-2 ${
                        activeAgent === tab.id ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {tab.label}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        activeAgent === tab.id ? 'bg-blue-500/20 text-blue-300' : 'bg-slate-700 text-slate-400'
                      }`}>{s.count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="p-4">
              {sortedFindings.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-sm">
                  <CheckCircle size={32} className="mx-auto mb-2 opacity-40" />
                  No findings for this agent
                </div>
              ) : (
                <div className="space-y-2">
                  {sortedFindings.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 p-3 rounded-xl bg-slate-800/40 border border-slate-700/40 hover:border-slate-600/60 cursor-pointer transition-all"
                      onClick={() => setSelectedFinding(f)}
                    >
                      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                        f.severity === 'critical' ? 'bg-red-500' :
                        f.severity === 'high' ? 'bg-orange-500' :
                        f.severity === 'medium' ? 'bg-yellow-500' :
                        f.severity === 'low' ? 'bg-blue-500' : 'bg-slate-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-sm font-medium text-slate-200">{f.finding_type}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${sevColor[f.severity]}`}>{f.severity}</span>
                          <ConfidenceBadge score={f.confidence} />
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2">{f.description}</p>
                        {f.affected_field && (
                          <span className="text-[10px] text-slate-500 mt-1">Field: <span className="font-mono text-slate-400">{f.affected_field}</span></span>
                        )}
                      </div>
                      <ChevronRight size={14} className="text-slate-600 mt-0.5 shrink-0" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>

          {/* Artifacts */}
          {artifacts.length > 0 && (
            <GlassCard className="p-4">
              <h3 className="text-sm font-semibold text-slate-200 font-space flex items-center gap-2 mb-3">
                <FileText size={15} className="text-blue-400" /> Generated Artifacts
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {artifacts.map((a, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 hover:border-blue-500/30 transition-colors group cursor-pointer">
                    <FileText size={16} className="text-blue-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-200 truncate">{a.name}</div>
                      <div className="text-xs text-slate-500">{a.type} · {a.size}</div>
                    </div>
                    <Download size={13} className="text-slate-600 group-hover:text-blue-400 transition-colors" />
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </>
      )}

      {/* Finding Detail Modal */}
      <Modal open={!!selectedFinding} onClose={() => setSelectedFinding(null)} title="Finding Detail">
        {selectedFinding && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded border ${sevColor[selectedFinding.severity]}`}>
                {selectedFinding.severity.toUpperCase()}
              </span>
              <ConfidenceBadge score={selectedFinding.confidence} />
              <span className="text-xs text-slate-500">· {agentLabel(selectedFinding.agent)}</span>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Finding Type</div>
              <div className="text-sm font-medium text-slate-200">{selectedFinding.finding_type}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Description</div>
              <p className="text-sm text-slate-300">{selectedFinding.description}</p>
            </div>
            {selectedFinding.recommendation && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Recommendation</div>
                <p className="text-sm text-slate-300 bg-slate-800/50 p-3 rounded-lg">{selectedFinding.recommendation}</p>
              </div>
            )}
            {selectedFinding.affected_field && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Affected Field</div>
                <code className="text-sm text-blue-300 font-mono bg-slate-800 px-2 py-1 rounded">{selectedFinding.affected_field}</code>
              </div>
            )}
            {selectedFinding.record_ids?.length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Affected Records ({selectedFinding.record_ids.length})</div>
                <div className="flex flex-wrap gap-1">
                  {selectedFinding.record_ids.map((id: string, i: number) => (
                    <code key={i} className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-mono">{id}</code>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Approve/Reject Modal */}
      <Modal
        open={!!decisionModal}
        onClose={() => { setDecisionModal(null); setDecisionNote(''); }}
        title={decisionModal === 'approve' ? '✓ Approve Pipeline Run' : '✗ Reject Pipeline Run'}
      >
        <div className="space-y-4">
          <div className={`p-3 rounded-lg text-sm ${
            decisionModal === 'approve' ? 'bg-green-500/10 border border-green-500/30 text-green-300' : 'bg-red-500/10 border border-red-500/30 text-red-300'
          }`}>
            {decisionModal === 'approve'
              ? 'Approving this run will unlock the Dashboard and mark the analysis as complete. This action is recorded in the audit log.'
              : 'Rejecting this run will flag it for re-processing. Please provide a reason below.'}
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">
              {decisionModal === 'approve' ? 'Approval Notes (optional)' : 'Rejection Reason *'}
            </label>
            <textarea
              value={decisionNote}
              onChange={e => setDecisionNote(e.target.value)}
              rows={3}
              placeholder={decisionModal === 'approve' ? 'e.g. All findings reviewed, compliant with protocol...' : 'e.g. Critical compliance violations need resolution...'}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button
              onClick={() => { setDecisionModal(null); setDecisionNote(''); }}
              className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDecision}
              disabled={submitting || (decisionModal === 'reject' && !decisionNote.trim())}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                decisionModal === 'approve'
                  ? 'bg-green-600 hover:bg-green-500 text-white'
                  : 'bg-red-600 hover:bg-red-500 text-white'
              }`}
            >
              {submitting ? 'Submitting...' : decisionModal === 'approve' ? 'Confirm Approval' : 'Confirm Rejection'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
