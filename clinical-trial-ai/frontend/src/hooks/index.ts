import { useState, useEffect, useRef } from 'react';
import { pipelineApi, streamingApi, alertsApi } from '../lib/api';
import { PipelineStatus, StreamingStatus, Alert } from '../lib/types';

// Pipeline status poller
export function usePipelineStatus(runId: string | null, enabled = true) {
  const [data, setData] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId || !enabled) { timerRef.current && clearInterval(timerRef.current); return; }
    setLoading(true);
    const poll = () => {
      pipelineApi.getStatus(runId).then(d => {
        setData(d); setLoading(false);
        if (d.status === 'completed' || d.status === 'failed') {
          timerRef.current && clearInterval(timerRef.current);
        }
      }).catch(() => setLoading(false));
    };
    poll();
    timerRef.current = setInterval(poll, 2000);
    return () => { timerRef.current && clearInterval(timerRef.current); };
  }, [runId, enabled]);

  return { data, loading };
}

// Streaming status poller
export function useStreamingStatus(runId: string | null) {
  const [data, setData] = useState<StreamingStatus | null>(null);
  useEffect(() => {
    if (!runId) return;
    const poll = () => streamingApi.getStatus(runId).then(setData).catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [runId]);
  return data;
}

// Alerts poller — returns flat array (backend now returns array directly)
export function useAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const poll = () => {
      alertsApi.getAlerts({}).then((d: any) => {
        // backend returns flat array
        if (Array.isArray(d)) setAlerts(d);
        else if (d.alerts) setAlerts(d.alerts);
      }).catch(() => {});
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  const unreadCount = alerts.filter(a => a.status === 'active' && !a.read).length;
  return { alerts, unreadCount };
}

// Active run poller
export function useActiveRun() {
  const [activeRun, setActiveRun] = useState<any | null>(null);

  useEffect(() => {
    const poll = () => pipelineApi.getActiveRun().then(setActiveRun).catch(() => {});
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  return activeRun;
}
