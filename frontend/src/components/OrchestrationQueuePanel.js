import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Play, RefreshCw, Activity, CheckCircle2, CircleDashed, AlertTriangle } from 'lucide-react';

async function readResponse(resp) {
  const text = await resp.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function statusIcon(status) {
  if (status === 'complete') return CheckCircle2;
  if (status === 'failed') return AlertTriangle;
  if (status === 'running') return Activity;
  return CircleDashed;
}

export default function OrchestrationQueuePanel({ api, token }) {
  const [queue, setQueue] = useState([]);
  const [prompt, setPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  const headers = useMemo(() => ({ 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }), [token]);

  const refreshQueue = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/orchestration/queue`, { headers });
      const data = await readResponse(resp);
      if (resp.ok) {
        setQueue(data.queue || []);
        setFetchError(null);
      } else {
        setFetchError(data.detail || data.message || `Queue unavailable (${resp.status})`);
      }
    } catch (error) {
      setFetchError(error.message);
    }
  }, [api, headers]);

  useEffect(() => {
    refreshQueue();
    const interval = setInterval(refreshQueue, 4000);
    return () => clearInterval(interval);
  }, [refreshQueue]);

  const enqueue = async () => {
    const taskPrompt = prompt.trim();
    if (!taskPrompt) return;
    setSubmitting(true);
    try {
      const resp = await fetch(`${api}/api/orchestration/queue`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ prompt: taskPrompt }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Unable to queue task');
      setPrompt('');
      await refreshQueue();
    } catch (error) {
      setFetchError(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="border border-cyan-900/50 bg-slate-950/70 p-4 flex flex-col gap-3" data-testid="orchestration-queue-panel">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-cyan-400" />
          <div className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Agent Queue</div>
        </div>
        <button
          type="button"
          onClick={refreshQueue}
          className="p-1.5 border border-cyan-900/40 text-cyan-300/60 hover:text-cyan-100 hover:border-cyan-400/40 transition-all"
          title="Refresh queue"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      <div className="flex gap-2">
        <input
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Queue a task, plan, or command…"
          className="flex-1 bg-slate-950/80 border border-cyan-900/40 px-3 py-2 text-[10px] font-mono text-cyan-100 outline-none placeholder:text-cyan-300/30"
        />
        <button
          type="button"
          onClick={enqueue}
          disabled={submitting || !prompt.trim()}
          className="px-3 py-2 border border-cyan-400/40 text-[10px] font-display tracking-[0.18em] uppercase text-cyan-100 hover:bg-cyan-950/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          <Play size={12} className="inline-block mr-1" /> Queue
        </button>
      </div>

      {fetchError && <div className="text-[9px] font-mono text-red-400/80">{fetchError}</div>}

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {queue.length === 0 ? (
          <div className="border border-cyan-900/20 px-3 py-4 text-center text-[9px] font-mono text-cyan-300/35">No queued tasks yet.</div>
        ) : queue.map((item) => {
          const Icon = statusIcon(item.status);
          return (
            <div key={item.id} className="border border-cyan-900/30 bg-black/30 px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <Icon size={12} className={item.status === 'failed' ? 'text-red-400' : item.status === 'complete' ? 'text-green-400' : 'text-cyan-400'} />
                  <div className="truncate font-mono text-[10px] text-cyan-100">{item.label || item.prompt}</div>
                </div>
                <div className="font-display text-[9px] tracking-[0.18em] uppercase text-cyan-300/40">{item.status}</div>
              </div>
              {item.summary && <div className="mt-1 text-[9px] font-mono text-cyan-300/50 line-clamp-2">{item.summary}</div>}
              {item.error && <div className="mt-1 text-[9px] font-mono text-red-400/80">{item.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
