import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import ArcReactor from './ArcReactor';
import Terminal from './Terminal';
import SystemDiagnostics from './SystemDiagnostics';
import WeatherWidget from './WeatherWidget';
import CalendarWidget from './CalendarWidget';
import StatusPanel from './StatusPanel';
import DevWorkspace from './DevWorkspace';
import SettingsPanel from './SettingsPanel';
import BottomDock from './BottomDock';
import { Activity, Cpu, Cloud, Code2, Terminal as TermIcon, Settings, Zap } from 'lucide-react';

export default function Dashboard({ token, api, onLogout }) {
  const [metrics, setMetrics] = useState(null);
  const [weather, setWeather] = useState(null);
  const [status, setStatus] = useState(null);
  const [activePanel, setActivePanel] = useState('terminal');

  const fetchMetrics = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/system/metrics`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) setMetrics(await resp.json());
    } catch (e) { /* silent */ }
  }, [api, token]);

  const fetchWeather = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/weather`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) setWeather(await resp.json());
    } catch (e) { /* silent */ }
  }, [api, token]);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/status`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      });
      if (resp.ok) setStatus(await resp.json());
    } catch (e) { /* silent */ }
  }, [api, token]);

  useEffect(() => {
    fetchMetrics();
    fetchWeather();
    fetchStatus();
    const metricsInterval = setInterval(fetchMetrics, 3000);
    const weatherInterval = setInterval(fetchWeather, 300000);
    const statusInterval = setInterval(fetchStatus, 10000);
    return () => {
      clearInterval(metricsInterval);
      clearInterval(weatherInterval);
      clearInterval(statusInterval);
    };
  }, [fetchMetrics, fetchWeather, fetchStatus]);

  return (
    <div className="h-screen flex flex-col overflow-hidden" data-testid="jarvis-dashboard">
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
          <div className="flex items-center gap-2 px-3 py-1 border border-green-500/30 rounded-sm" data-testid="status-indicator">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="font-mono text-[10px] tracking-widest text-green-400">ONLINE</span>
          </div>
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
              {activePanel === 'terminal' && <Terminal api={api} token={token} />}
              {activePanel === 'developer' && <DevWorkspace api={api} token={token} />}
              {activePanel === 'settings' && <SettingsPanel api={api} token={token} />}
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
