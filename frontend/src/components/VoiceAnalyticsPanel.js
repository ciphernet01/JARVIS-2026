import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Zap } from 'lucide-react';
import {
  Area,
  AreaChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const DEFAULT_HISTORY = [];

function buildWsUrl(api, token) {
  const base = api || window.location.origin;
  const wsBase = base.replace(/^http/, 'ws');
  const url = new URL('/api/voice/stream', wsBase);
  url.searchParams.set('token', token);
  return url.toString();
}

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function StatPill({ label, value, accent }) {
  return (
    <div className="flex flex-col gap-1 px-3 py-2 border border-cyan-900/40 bg-slate-950/60">
      <span className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-300/60">{label}</span>
      <span className="font-mono text-[13px]" style={{ color: accent }}>{value}</span>
    </div>
  );
}

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function toCsv(entries) {
  const header = ['command', 'response', 'confidence', 'status', 'duration_ms', 'timestamp'];
  const rows = entries.map((entry) => [
    entry.command || '',
    entry.response || '',
    entry.confidence ?? '',
    entry.status || '',
    entry.duration_ms ?? '',
    entry.timestamp || '',
  ]);
  return [header, ...rows]
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
    .join('\n');
}

function Sparkline({ points, stroke, fill, label, unit }) {
  const width = 240;
  const height = 60;
  if (!points || points.length === 0) {
    return (
      <div className="border border-cyan-900/40 bg-slate-950/60 p-3">
        <div className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-300/70">{label}</div>
        <div className="mt-2 h-[60px] flex items-center justify-center text-[10px] font-mono text-cyan-500/50">No signal yet</div>
      </div>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = width / (points.length - 1 || 1);

  const path = points
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');

  const areaPath = `${path} L ${width} ${height} L 0 ${height} Z`;
  const latest = points[points.length - 1];

  return (
    <div className="border border-cyan-900/40 bg-slate-950/60 p-3">
      <div className="flex items-center justify-between">
        <div className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-300/70">{label}</div>
        <div className="font-mono text-[10px]" style={{ color: stroke }}>{latest}{unit}</div>
      </div>
      <svg width={width} height={height} className="mt-2">
        <defs>
          <linearGradient id={`${label}-fill`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={fill} stopOpacity="0.5" />
            <stop offset="100%" stopColor={fill} stopOpacity="0.1" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${label}-fill)`} opacity="0.6" />
        <path d={path} fill="none" stroke={stroke} strokeWidth="2" />
      </svg>
    </div>
  );
}

function HistoryRow({ entry }) {
  const status = (entry.status || '').toLowerCase();
  const statusTone = status === 'executed'
    ? 'text-emerald-300 border-emerald-400/40'
    : status === 'failed'
      ? 'text-rose-300 border-rose-400/40'
      : 'text-cyan-300/60 border-cyan-400/20';

  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 border border-cyan-900/30 bg-slate-950/50 px-3 py-2">
      <div>
        <div className="font-display text-[9px] tracking-[0.18em] uppercase text-cyan-300/60">{entry.command || '—'}</div>
        <div className="font-mono text-[11px] text-cyan-100/70 truncate">{entry.response || 'No response'}</div>
      </div>
      <div className="text-right">
        <div className={`inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-display tracking-[0.2em] uppercase border ${statusTone}`}>
          {status || 'unknown'}
        </div>
        <div className="font-mono text-[10px] text-emerald-300/70">{Math.round((entry.confidence || 0) * 100)}%</div>
        <div className="font-mono text-[10px] text-cyan-300/60">{entry.duration_ms || 0}ms</div>
        <div className="font-mono text-[9px] text-cyan-500/50">{formatTime(entry.timestamp)}</div>
      </div>
    </div>
  );
}

export default function VoiceAnalyticsPanel({ api, token }) {
  const [history, setHistory] = useState(DEFAULT_HISTORY);
  const [stats, setStats] = useState(null);
  const [context, setContext] = useState(null);
  const [streamState, setStreamState] = useState('offline');
  const [clearing, setClearing] = useState(false);
  const [latencyTrend, setLatencyTrend] = useState([]);
  const [confidenceTrend, setConfidenceTrend] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [minConfidence, setMinConfidence] = useState(0);
  const [exportBusy, setExportBusy] = useState(false);
  const wsRef = useRef(null);
  const pollRef = useRef(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const [historyResp, statsResp, contextResp] = await Promise.all([
        fetch(`${api}/api/voice/history?limit=20`, { headers: { 'X-JARVIS-TOKEN': token } }),
        fetch(`${api}/api/voice/stats`, { headers: { 'X-JARVIS-TOKEN': token } }),
        fetch(`${api}/api/voice/context`, { headers: { 'X-JARVIS-TOKEN': token } }),
      ]);

      if (historyResp.ok) {
        const payload = await historyResp.json();
        setHistory(payload.history || DEFAULT_HISTORY);
      }

      if (statsResp.ok) {
        const payload = await statsResp.json();
        setStats(payload);
      }

      if (contextResp.ok) {
        const payload = await contextResp.json();
        setContext(payload.session || null);
      }
    } catch (err) {
      setStreamState('offline');
    }
  }, [api, token]);

  const updateTrends = useCallback((nextHistory) => {
    const entries = nextHistory || [];
    const latency = entries.map((entry) => entry.duration_ms || 0).reverse();
    const confidence = entries.map((entry) => Math.round((entry.confidence || 0) * 100)).reverse();

    setLatencyTrend((prev) => {
      const merged = [...prev, ...latency].slice(-20);
      return merged.length ? merged : prev;
    });

    setConfidenceTrend((prev) => {
      const merged = [...prev, ...confidence].slice(-20);
      return merged.length ? merged : prev;
    });
  }, []);

  const handleClear = useCallback(async (hours) => {
    setClearing(true);
    try {
      await fetch(`${api}/api/voice/history?older_than_hours=${hours}`, {
        method: 'DELETE',
        headers: { 'X-JARVIS-TOKEN': token },
      });
      await fetchSnapshot();
    } finally {
      setClearing(false);
    }
  }, [api, token, fetchSnapshot]);

  const handleExport = useCallback((format, entries) => {
    if (!entries.length) return;
    setExportBusy(true);
    try {
      if (format === 'csv') {
        downloadFile(toCsv(entries), `jarvis_voice_history_${Date.now()}.csv`, 'text/csv');
      } else {
        downloadFile(JSON.stringify(entries, null, 2), `jarvis_voice_history_${Date.now()}.json`, 'application/json');
      }
    } finally {
      setExportBusy(false);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot();

    const wsUrl = buildWsUrl(api, token);
    let ws;

    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setStreamState('connecting');

      ws.onopen = () => setStreamState('live');
      ws.onclose = () => setStreamState('offline');
      ws.onerror = () => setStreamState('offline');

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.history) {
            setHistory(payload.history);
            updateTrends(payload.history);
          }
          if (payload.stats) setStats(payload.stats);
          if (payload.context) setContext(payload.context);
        } catch (err) {
          // Ignore parse errors
        }
      };
    } catch (err) {
      setStreamState('offline');
    }

    pollRef.current = setInterval(fetchSnapshot, 5000);

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [api, token, fetchSnapshot, updateTrends]);

  const filteredHistory = history.filter((entry) => {
    const text = `${entry.command || ''} ${entry.response || ''}`.toLowerCase();
    const queryMatch = text.includes(searchQuery.toLowerCase().trim());
    const statusMatch = statusFilter === 'all' || (entry.status || '').toLowerCase() === statusFilter;
    const confidenceMatch = (entry.confidence || 0) * 100 >= minConfidence;
    return queryMatch && statusMatch && confidenceMatch;
  });

  const historyRows = filteredHistory.slice(0, 8);
  const historyStats = stats?.history_stats || {};
  const perfStats = stats?.performance_stats || {};
  const alertItems = [];
  if ((historyStats.success_rate || 0) < 0.9 && historyStats.total_entries > 10) {
    alertItems.push('Success rate below 90%');
  }
  if ((perfStats.p95_duration_ms || 0) > 500) {
    alertItems.push('P95 latency above 500ms');
  }
  if ((historyStats.avg_latency_ms || 0) > 300) {
    alertItems.push('Average latency above 300ms');
  }
  const chartData = filteredHistory.slice(-20).map((entry, index) => ({
    index: index + 1,
    latency: entry.duration_ms || 0,
    confidence: Math.round((entry.confidence || 0) * 100),
  }));

  return (
    <div className="h-full flex flex-col gap-3 p-4 overflow-hidden" data-testid="voice-analytics">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-display text-[11px] tracking-[0.2em] uppercase text-cyan-300/60">Voice Analytics</div>
          <div className="font-display text-lg text-cyan-100" style={{ textShadow: '0 0 16px rgba(16,185,129,0.4)' }}>
            Neural Telemetry Grid
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1 border border-cyan-900/40 bg-slate-950/70">
            <span className={`w-2 h-2 rounded-full ${streamState === 'live' ? 'bg-emerald-400 animate-pulse' : streamState === 'connecting' ? 'bg-amber-400 animate-pulse' : 'bg-red-400'}`} />
            <span className="font-mono text-[10px] tracking-widest text-cyan-300/60">{streamState.toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleClear(1)}
              disabled={clearing}
              className="px-3 py-1 border border-cyan-900/40 text-[9px] font-display tracking-[0.2em] uppercase text-cyan-300/60 hover:text-cyan-100 disabled:opacity-50"
            >
              Clear 1h
            </button>
            <button
              type="button"
              onClick={() => handleClear(24)}
              disabled={clearing}
              className="px-3 py-1 border border-cyan-900/40 text-[9px] font-display tracking-[0.2em] uppercase text-cyan-300/60 hover:text-cyan-100 disabled:opacity-50"
            >
              Clear 24h
            </button>
            <button
              type="button"
              onClick={() => handleClear(0)}
              disabled={clearing}
              className="px-3 py-1 border border-rose-900/40 text-[9px] font-display tracking-[0.2em] uppercase text-rose-300/70 hover:text-rose-200 disabled:opacity-50"
            >
              Clear All
            </button>
            <button
              type="button"
              onClick={() => handleExport('json', filteredHistory)}
              disabled={exportBusy}
              className="px-3 py-1 border border-cyan-900/40 text-[9px] font-display tracking-[0.2em] uppercase text-cyan-300/60 hover:text-cyan-100 disabled:opacity-50"
            >
              Export JSON
            </button>
            <button
              type="button"
              onClick={() => handleExport('csv', filteredHistory)}
              disabled={exportBusy}
              className="px-3 py-1 border border-cyan-900/40 text-[9px] font-display tracking-[0.2em] uppercase text-cyan-300/60 hover:text-cyan-100 disabled:opacity-50"
            >
              Export CSV
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatPill label="Success Rate" value={`${Math.round((historyStats.success_rate || 0) * 100)}%`} accent="#22d3ee" />
        <StatPill label="Avg Latency" value={`${historyStats.avg_latency_ms || 0}ms`} accent="#f472b6" />
        <StatPill label="P95" value={`${perfStats.p95_duration_ms || 0}ms`} accent="#facc15" />
        <StatPill label="Commands" value={historyStats.total_entries || 0} accent="#34d399" />
        <StatPill label="Failures" value={historyStats.failed || 0} accent="#fb7185" />
        <StatPill label="Confidence" value={`${Math.round((historyStats.avg_confidence || 0) * 100)}%`} accent="#a78bfa" />
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-3 flex-1 overflow-hidden">
        <div className="flex flex-col gap-2 overflow-hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-cyan-300" />
              <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Recent Commands</span>
            </div>
            <span className="font-mono text-[9px] text-cyan-500/60">Showing {historyRows.length} / {filteredHistory.length}</span>
          </div>
          <div className="grid grid-cols-[1.4fr_0.8fr_0.8fr] gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search command or response"
              className="px-3 py-2 border border-cyan-900/40 bg-slate-950/70 text-[10px] font-mono text-cyan-100/70 placeholder:text-cyan-600/60 focus:outline-none focus:border-cyan-400"
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="px-3 py-2 border border-cyan-900/40 bg-slate-950/70 text-[10px] font-mono text-cyan-100/70 focus:outline-none focus:border-cyan-400"
            >
              <option value="all">All Status</option>
              <option value="executed">Executed</option>
              <option value="failed">Failed</option>
              <option value="recognized">Recognized</option>
              <option value="processing">Processing</option>
              <option value="skipped">Skipped</option>
            </select>
            <div className="flex items-center gap-2 px-3 py-2 border border-cyan-900/40 bg-slate-950/70">
              <span className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-400/70">Min</span>
              <input
                type="range"
                min="0"
                max="100"
                value={minConfidence}
                onChange={(event) => setMinConfidence(Number(event.target.value))}
                className="flex-1 accent-cyan-400"
              />
              <span className="font-mono text-[10px] text-cyan-200/70">{minConfidence}%</span>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {historyRows.length === 0 && (
              <div className="border border-cyan-900/30 bg-slate-950/50 px-3 py-6 text-center text-cyan-400/50 text-xs font-mono">
                No commands match your filters.
              </div>
            )}
            {historyRows.map((entry, index) => (
              <HistoryRow key={`${entry.command}-${index}`} entry={entry} />
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="border border-cyan-900/40 bg-slate-950/60 p-3">
            <div className="flex items-center justify-between">
              <div className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-300/70">Signal Chart</div>
              <div className="font-mono text-[9px] text-cyan-500/60">Last 20</div>
            </div>
            <div className="mt-2 h-[140px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="latencyFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="index" hide />
                  <YAxis hide />
                  <Tooltip
                    cursor={{ stroke: '#22d3ee', strokeWidth: 0.5, opacity: 0.4 }}
                    contentStyle={{ background: '#020617', border: '1px solid rgba(34,211,238,0.4)', fontSize: '10px' }}
                    labelStyle={{ color: '#a5f3fc' }}
                    formatter={(value, name) => [value, name === 'latency' ? 'Latency (ms)' : 'Confidence (%)']}
                  />
                  <Area type="monotone" dataKey="latency" stroke="#22d3ee" fill="url(#latencyFill)" strokeWidth={2} />
                  <Line type="monotone" dataKey="confidence" stroke="#f472b6" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <Sparkline
            points={latencyTrend}
            stroke="#22d3ee"
            fill="#0ea5e9"
            label="Latency Trace"
            unit="ms"
          />
          <Sparkline
            points={confidenceTrend}
            stroke="#f472b6"
            fill="#ec4899"
            label="Confidence Wave"
            unit="%"
          />
          {alertItems.length > 0 && (
            <div className="border border-rose-900/50 bg-rose-950/40 p-3">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={14} className="text-rose-300" />
                <span className="font-display text-[10px] tracking-[0.2em] uppercase text-rose-300/80">Alerts</span>
              </div>
              <div className="space-y-1">
                {alertItems.map((item) => (
                  <div key={item} className="font-mono text-[10px] text-rose-200/70">• {item}</div>
                ))}
              </div>
            </div>
          )}
          <div className="border border-cyan-900/40 bg-slate-950/60 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={14} className="text-emerald-300" />
              <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Session Context</span>
            </div>
            {context ? (
              <div className="space-y-2">
                <div className="font-mono text-[10px] text-cyan-100/70">Session: {context.session_id}</div>
                <div className="font-mono text-[10px] text-cyan-300/60">Turns: {context.turn_count}</div>
                <div className="font-mono text-[10px] text-cyan-300/60">Duration: {context.duration_minutes}m</div>
                <div className="font-mono text-[10px] text-cyan-300/60">Intent: {context.current_intent || '—'}</div>
                <div className="font-mono text-[10px] text-cyan-300/60">Prefs: {Object.keys(context.user_preferences || {}).length}</div>
              </div>
            ) : (
              <div className="font-mono text-[10px] text-cyan-500/50">Context unavailable.</div>
            )}
          </div>

          <div className="border border-cyan-900/40 bg-gradient-to-br from-slate-950 via-slate-950 to-cyan-950/30 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Zap size={14} className="text-yellow-300" />
              <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Live Pulse</span>
            </div>
            <div className="space-y-2">
              <div className="font-mono text-[10px] text-cyan-300/60">Operations: {perfStats.count || 0}</div>
              <div className="font-mono text-[10px] text-cyan-300/60">Success: {Math.round((perfStats.success_rate || 0) * 100)}%</div>
              <div className="font-mono text-[10px] text-cyan-300/60">Avg: {perfStats.avg_duration_ms || 0}ms</div>
            </div>
            <div className="mt-3 h-1 w-full bg-cyan-900/50 overflow-hidden">
              <div className="h-full bg-gradient-to-r from-cyan-400 via-fuchsia-400 to-emerald-400 animate-pulse" style={{ width: `${Math.min(100, (perfStats.success_rate || 0) * 100)}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
