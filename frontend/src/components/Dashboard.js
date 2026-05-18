import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import ArcReactor from './ArcReactor';
import Terminal from './Terminal';
import SystemDiagnostics from './SystemDiagnostics';
import WeatherWidget from './WeatherWidget';
import CalendarWidget from './CalendarWidget';
import StatusPanel from './StatusPanel';
import DevWorkspace from './DevWorkspace';
import FilesystemExplorer from './FilesystemExplorer';
import SystemControlPanel from './SystemControlPanel';
import VoiceAnalyticsPanel from './VoiceAnalyticsPanel';
import SettingsPanel from './SettingsPanel';
import BottomDock from './BottomDock';
import { Code2, Terminal as TermIcon, Settings, Zap, FolderOpen, ShieldCheck } from 'lucide-react';

function normalizeApiBase(api) {
  if (typeof api !== 'string') return '';
  const trimmed = api.trim();
  if (!trimmed || trimmed === '/' || trimmed === 'undefined' || trimmed === 'null') return '';
  return trimmed.replace(/\/+$/, '');
}

export default function Dashboard({ token, api, onLogout, initialPanel = 'control', preferences, onPreferencesChange }) {
  const [metrics, setMetrics] = useState(null);
  const [weather, setWeather] = useState(null);
  const [status, setStatus] = useState(null);
  const [activePanel, setActivePanel] = useState(initialPanel);
  const [biosMode, setBiosMode] = useState(false);

  const [fetchError, setFetchError] = useState(null);
  const [telemetryFetching, setTelemetryFetching] = useState(false);
  const metricsInFlight = useRef(false);
  const weatherInFlight = useRef(false);
  const statusInFlight = useRef(false);
  const apiBase = useMemo(() => normalizeApiBase(api), [api]);
  const telemetryRefreshMs = Math.max(3, Math.min(30, preferences?.telemetry_refresh_seconds || 5)) * 1000;

  const fetchMetrics = useCallback(async () => {
    if (metricsInFlight.current) return;
    metricsInFlight.current = true;
    setTelemetryFetching(true);
    try {
      const resp = await fetch(`${apiBase}/api/system/metrics`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) {
        setMetrics(await resp.json());
        setFetchError(null);
      } else if (resp.status === 401) {
        onLogout();
      } else {
        setFetchError(`Telemetry fetch failed (${resp.status})`);
      }
    } catch (e) {
      setFetchError(`Telemetry connection unstable: ${e.message}`);
    } finally {
      metricsInFlight.current = false;
      setTelemetryFetching(false);
    }
  }, [apiBase, token, onLogout]);

  const fetchWeather = useCallback(async () => {
    if (weatherInFlight.current) return;
    weatherInFlight.current = true;
    try {
      const resp = await fetch(`${apiBase}/api/weather`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) setWeather(await resp.json());
    } catch (e) { /* non-critical panel */ }
    finally { weatherInFlight.current = false; }
  }, [apiBase, token]);

  const fetchStatus = useCallback(async () => {
    if (statusInFlight.current) return;
    statusInFlight.current = true;
    try {
      const resp = await fetch(`${apiBase}/api/status`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) setStatus(await resp.json());
    } catch (e) { /* non-critical panel */ }
    finally { statusInFlight.current = false; }
  }, [apiBase, token]);

  useEffect(() => {
    fetchMetrics();
    fetchWeather();
    fetchStatus();
    const metricsInterval = setInterval(fetchMetrics, telemetryRefreshMs);
    const weatherInterval = setInterval(fetchWeather, 300000);
    const statusInterval = setInterval(fetchStatus, 10000);
    return () => {
      clearInterval(metricsInterval);
      clearInterval(weatherInterval);
      clearInterval(statusInterval);
    };
  }, [fetchMetrics, fetchWeather, fetchStatus, telemetryRefreshMs]);

  useEffect(() => {
    setActivePanel(initialPanel);
  }, [initialPanel]);

  return (
    <div className={`h-screen flex flex-col overflow-hidden ${biosMode ? 'bios-mode' : ''}`} data-testid="jarvis-dashboard">
      {/* Top Bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-cyan-900/50 bg-slate-950/80 backdrop-blur-xl z-40" data-testid="top-bar">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-lg tracking-tighter uppercase text-cyan-400" style={{ textShadow: '0 0 10px rgba(6,182,212,0.4)' }}>
            J.A.R.V.I.S
          </h1>
          <span className="w-px h-5 bg-cyan-500/40" />
          <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/50">Sypher Industries // Neural Interface v2.0</span>
        </div>
        <div className="flex items-center gap-4">
          {fetchError && (
            <div className="flex items-center gap-2 px-3 py-1 border border-red-500/30 rounded-sm" data-testid="error-indicator">
              <span className="w-2 h-2 rounded-full bg-red-400" />
              <span className="font-mono text-[9px] tracking-tighter text-red-400 uppercase">{fetchError}</span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1 border border-green-500/30 rounded-sm" data-testid="status-indicator">
            <span className={`w-2 h-2 rounded-full ${fetchError ? 'bg-amber-400' : 'bg-green-400'} animate-pulse`} />
            <span className={`font-mono text-[10px] tracking-widest ${fetchError ? 'text-amber-400' : 'text-green-400'}`}>{fetchError ? 'DEGRADED' : 'ONLINE'}</span>
          </div>
          <button
            type="button"
            onClick={() => setBiosMode((prev) => !prev)}
            className={`px-3 py-1 border text-[10px] font-display tracking-[0.25em] uppercase transition-all ${
              biosMode ? 'border-fuchsia-400/60 text-fuchsia-300 bg-fuchsia-950/40' : 'border-cyan-900/40 text-cyan-300/60 hover:text-cyan-100'
            }`}
          >
            BIOS MODE
          </button>
          <Clock />
        </div>
      </header>

      {/* Main Grid */}
      <main className="flex-1 grid grid-cols-12 gap-3 p-3 overflow-hidden">
        {/* Left Column - 3 cols */}
        <div className="col-span-3 flex flex-col gap-3 overflow-y-auto">
          <CalendarWidget />
          <SystemDiagnostics metrics={metrics} />
        </div>

        {/* Center Column - 6 cols */}
        <div className="col-span-6 flex flex-col gap-3 overflow-hidden">
          {/* Arc Reactor + Status */}
          <div className="flex items-center justify-center py-2">
            <ArcReactor />
          </div>

          {/* Terminal / Dev Workspace Toggle */}
          <div className="flex-1 flex flex-col overflow-hidden border border-cyan-900/50 bg-slate-950/80">
            <div className="flex border-b border-cyan-900/50">
              <button
                onClick={() => setActivePanel('terminal')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'terminal' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-terminal"
              >
                <TermIcon size={14} /> Command Terminal
              </button>
              <button
                onClick={() => setActivePanel('control')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'control' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-control"
              >
                <ShieldCheck size={14} /> OS Control
              </button>
              <button
                onClick={() => setActivePanel('filesystem')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'filesystem' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-filesystem"
              >
                <FolderOpen size={14} /> Filesystem
              </button>
              <button
                onClick={() => setActivePanel('analytics')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'analytics' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-analytics"
              >
                <Zap size={14} /> Analytics
              </button>
              <button
                onClick={() => setActivePanel('developer')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'developer' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-developer"
              >
                <Code2 size={14} /> Developer Mode
              </button>
              <button
                onClick={() => setActivePanel('settings')}
                className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
                  activePanel === 'settings' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
                }`}
                data-testid="tab-settings"
              >
                <Settings size={14} /> Settings
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {activePanel === 'control' && <SystemControlPanel api={apiBase} token={token} dashboardMetrics={metrics} telemetryFetching={telemetryFetching} refreshSeconds={preferences?.telemetry_refresh_seconds || 5} />}
              {activePanel === 'terminal' && <Terminal api={apiBase} token={token} />}
              {activePanel === 'filesystem' && <FilesystemExplorer api={apiBase} token={token} />}
              {activePanel === 'analytics' && <VoiceAnalyticsPanel api={apiBase} token={token} />}
              {activePanel === 'developer' && <DevWorkspace api={apiBase} token={token} />}
              {activePanel === 'settings' && <SettingsPanel api={apiBase} token={token} preferences={preferences} onPreferencesChange={onPreferencesChange} />}
            </div>
          </div>
        </div>

        {/* Right Column - 3 cols */}
        <div className="col-span-3 flex flex-col gap-3 overflow-y-auto">
          <WeatherWidget weather={weather} />
          <StatusPanel status={status} />
        </div>
      </main>

      {/* Bottom Dock */}
      <BottomDock activePanel={activePanel} setActivePanel={setActivePanel} onLogout={onLogout} />
    </div>
  );
}

function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const h = String(time.getHours()).padStart(2, '0');
  const m = String(time.getMinutes()).padStart(2, '0');
  const s = String(time.getSeconds()).padStart(2, '0');
  return (
    <div className="text-right">
      <div className="font-mono text-sm text-white" style={{ textShadow: '0 0 8px rgba(6,182,212,0.4)' }}>{h}:{m}:{s}</div>
      <div className="font-display text-[9px] tracking-widest text-cyan-300/50 uppercase">
        {time.toLocaleDateString('en-US', { weekday: 'short', day: '2-digit', month: 'short' })}
      </div>
    </div>
  );
}
