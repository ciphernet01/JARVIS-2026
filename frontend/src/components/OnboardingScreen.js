import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, DatabaseBackup, RefreshCw, ShieldCheck, Terminal } from 'lucide-react';

async function readResponse(resp) {
  const text = await resp.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

export default function OnboardingScreen({ api, token, onComplete, onOpenSettings }) {
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchReadiness = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const resp = await fetch(`${api}/api/os/readiness`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (!resp.ok) {
        setMessage({ success: false, text: data.detail || data.message || 'Readiness check failed.' });
      } else {
        setReadiness(data);
      }
    } catch (error) {
      setMessage({ success: false, text: `Readiness check failed: ${error.message}` });
    } finally {
      setLoading(false);
    }
  }, [api, token]);

  useEffect(() => {
    fetchReadiness();
  }, [fetchReadiness]);

  const createCheckpoint = async () => {
    setActionBusy(true);
    setMessage(null);
    try {
      const resp = await fetch(`${api}/api/os/safety/checkpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ label: 'first-run-checkpoint', notes: 'Created during first-run OS readiness setup.' }),
      });
      const data = await readResponse(resp);
      setMessage({ success: resp.ok, text: data.message || (resp.ok ? 'Checkpoint created.' : 'Checkpoint failed.') });
      await fetchReadiness();
    } catch (error) {
      setMessage({ success: false, text: `Checkpoint failed: ${error.message}` });
    } finally {
      setActionBusy(false);
    }
  };

  const completeSetup = () => {
    localStorage.setItem('jarvis_onboarding_complete', 'true');
    onComplete();
  };

  const items = readiness?.items || [];

  return (
    <div className="min-h-screen bg-slate-950 text-cyan-100 p-6 overflow-y-auto" data-testid="onboarding-screen">
      <div className="max-w-5xl mx-auto">
        <header className="flex items-center justify-between gap-4 border-b border-cyan-900/40 pb-4 mb-5">
          <div>
            <div className="font-display text-[10px] tracking-[0.28em] uppercase text-cyan-300/50 mb-2">JARVIS OS First Run</div>
            <h1 className="font-display text-2xl tracking-tight uppercase text-cyan-300">Operational Readiness</h1>
          </div>
          <div className="text-right">
            <div className="font-mono text-3xl text-cyan-100">{Math.round((readiness?.score || 0) * 100)}%</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-cyan-300/45">{readiness?.overall || 'scanning'}</div>
          </div>
        </header>

        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="border border-cyan-900/40 bg-slate-950/70 p-4">
            <ShieldCheck size={18} className="text-cyan-400 mb-2" />
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/40 mb-1">Safety Gates</div>
            <div className="font-mono text-sm text-cyan-100">Active before control-plane changes</div>
          </div>
          <div className="border border-cyan-900/40 bg-slate-950/70 p-4">
            <Terminal size={18} className="text-cyan-400 mb-2" />
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/40 mb-1">Operator Core</div>
            <div className="font-mono text-sm text-cyan-100">Apps, services, packages, hardware</div>
          </div>
          <div className="border border-cyan-900/40 bg-slate-950/70 p-4">
            <DatabaseBackup size={18} className="text-cyan-400 mb-2" />
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/40 mb-1">Recovery</div>
            <div className="font-mono text-sm text-cyan-100">Checkpoint before shipping changes</div>
          </div>
        </div>

        {message && (
          <div className={`mb-4 border p-3 font-mono text-[10px] ${message.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'}`}>
            {message.text}
          </div>
        )}

        <section className="border border-cyan-900/40 bg-black/20 mb-5">
          <div className="flex items-center justify-between p-3 border-b border-cyan-900/30">
            <div className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/60">Readiness Checklist</div>
            <button
              onClick={fetchReadiness}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 border border-cyan-900/50 text-cyan-300/60 font-display text-[9px] tracking-wider uppercase hover:text-cyan-200 disabled:opacity-40"
            >
              <RefreshCw size={11} /> {loading ? 'Scanning' : 'Rescan'}
            </button>
          </div>
          <div className="divide-y divide-cyan-900/20">
            {items.map((item) => (
              <div key={item.key} className="grid grid-cols-[28px_200px_1fr] gap-3 p-3 items-start">
                {item.status === 'pass' ? <CheckCircle2 size={16} className="text-green-400 mt-0.5" /> : <AlertTriangle size={16} className="text-amber-400 mt-0.5" />}
                <div className="font-display text-[10px] tracking-widest uppercase text-cyan-200">{item.label}</div>
                <div>
                  <div className="font-mono text-[10px] text-cyan-100/80">{item.detail}</div>
                  {item.action && <div className="font-mono text-[9px] text-amber-300/80 mt-1">{item.action}</div>}
                </div>
              </div>
            ))}
          </div>
        </section>

        <footer className="flex items-center justify-between gap-3">
          <div className="flex gap-2">
            <button
              onClick={createCheckpoint}
              disabled={actionBusy}
              className="flex items-center gap-2 px-4 py-2 border border-green-500/40 text-green-300 font-display text-[10px] tracking-widest uppercase hover:bg-green-950/20 disabled:opacity-40"
            >
              <DatabaseBackup size={13} /> Create Checkpoint
            </button>
            <button
              onClick={onOpenSettings}
              className="px-4 py-2 border border-cyan-900/50 text-cyan-300/70 font-display text-[10px] tracking-widest uppercase hover:text-cyan-200"
            >
              Open Settings
            </button>
          </div>
          <button
            onClick={completeSetup}
            disabled={readiness?.overall === 'blocked'}
            className="px-5 py-2 border border-cyan-500/50 text-cyan-200 bg-cyan-950/20 font-display text-[10px] tracking-widest uppercase hover:bg-cyan-950/40 disabled:opacity-40"
            data-testid="complete-onboarding"
          >
            Enter JARVIS OS
          </button>
        </footer>
      </div>
    </div>
  );
}
