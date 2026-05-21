import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import ArcReactor from './ArcReactor';
import Terminal from './Terminal';
import SystemDiagnostics from './SystemDiagnostics';
import WeatherWidget from './WeatherWidget';
import CalendarWidget from './CalendarWidget';
import StatusPanel from './StatusPanel';
import DevWorkspace from './DevWorkspace';
import FilesystemExplorer from './FilesystemExplorer';
import SystemControlHUD from './SystemControlHUD';
import VoiceAnalyticsPanel from './VoiceAnalyticsPanel';
import SettingsPanel from './SettingsPanel';
import GestureControlPanel from './GestureControlPanel';
import SpatialCursor from './SpatialCursor';
import BottomDock from './BottomDock';
import NeuralInsights from './NeuralInsights';
import BentoLauncher from './BentoLauncher';
import NotificationHUD from './NotificationHUD';
import OrchestrationQueuePanel from './OrchestrationQueuePanel';
import { Code2, Terminal as TermIcon, Settings, Zap, FolderOpen, ShieldCheck, Hand, Minus, X, LayoutGrid } from 'lucide-react';

function normalizeApiBase(api) {
  if (typeof api !== 'string') return '';
  const trimmed = api.trim();
  if (!trimmed || trimmed === '/' || trimmed === 'undefined' || trimmed === 'null') return '';
  return trimmed.replace(/\/+$/, '');
}

function buildWsUrl(apiBase, path) {
  if (!apiBase) {
    return `ws://${window.location.hostname}:8001${path}`;
  }
  return `${apiBase.replace(/^http/, 'ws')}${path}`;
}

function loadStoredValue(key, fallback) {
  if (typeof window === 'undefined') return fallback;
  try {
    const stored = window.localStorage.getItem(key);
    return stored == null ? fallback : JSON.parse(stored);
  } catch {
    return fallback;
  }
}

function saveStoredValue(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage failures in restricted browsers.
  }
}

function clampPoint(point, fallback) {
  if (!point || typeof point.x !== 'number' || typeof point.y !== 'number') return fallback;
  return {
    x: Math.max(16, Math.round(point.x)),
    y: Math.max(16, Math.round(point.y)),
  };
}

export default function Dashboard({ token, api, onLogout, initialPanel = 'control', preferences, onPreferencesChange }) {
  const [metrics, setMetrics] = useState(null);
  const [weather, setWeather] = useState(null);
  const [status, setStatus] = useState(null);
  const [activePanel, setActivePanel] = useState(initialPanel);
  const [biosMode, setBiosMode] = useState(false);
  const [focusedZone, setFocusedZone] = useState('center');
  const [spatialMode, setSpatialMode] = useState(() => {
    if (typeof window === 'undefined') return true;
    try {
      const stored = window.localStorage.getItem('astra.spatialMode');
      return stored == null ? false : stored === '1';
    } catch {
      return false;
    }
  });

  const [fetchError, setFetchError] = useState(null);
  const [telemetryFetching, setTelemetryFetching] = useState(false);
  const metricsInFlight = useRef(false);
  const weatherInFlight = useRef(false);
  const statusInFlight = useRef(false);
  const apiBase = useMemo(() => normalizeApiBase(api), [api]);
  const telemetryRefreshMs = Math.max(3, Math.min(30, preferences?.telemetry_refresh_seconds || 5)) * 1000;
  const launcherDragOffset = useRef({ x: 0, y: 0 });
  const centerDragOffset = useRef({ x: 0, y: 0 });
  const apiBaseRef = useRef(apiBase);

  const defaultLauncherPosition = useMemo(() => ({
    x: typeof window === 'undefined' ? 80 : Math.max(24, Math.round((window.innerWidth - 840) / 2)),
    y: typeof window === 'undefined' ? 72 : Math.max(48, Math.round((window.innerHeight - 520) / 2)),
  }), []);

  const [launcherPosition, setLauncherPosition] = useState(() => clampPoint(loadStoredValue('astra.launcherPosition', null), defaultLauncherPosition));
  const [overlayZ, setOverlayZ] = useState({ launcher: 110, center: 111 });
  
  const isDesktop = !!window.JARVIS_DESKTOP;
  const [isLauncherOpen, setIsLauncherOpen] = useState(false);
  const [lastGesture, setLastGesture] = useState('GESTURE_NONE');

  const raiseOverlay = useCallback((overlayName) => {
    setOverlayZ((prev) => {
      const top = Math.max(...Object.values(prev), 100) + 1;
      return { ...prev, [overlayName]: top };
    });
  }, []);

  const panelToZone = useMemo(() => ({
    control: 'center',
    terminal: 'center',
    analytics: 'center',
    developer: 'center',
    filesystem: 'right',
    settings: 'right',
    gesture: 'left',
  }), []);

  useEffect(() => {
    setFocusedZone(panelToZone[activePanel] || 'center');
  }, [activePanel, panelToZone]);

  useEffect(() => {
    saveStoredValue('astra.launcherPosition', launcherPosition);
  }, [launcherPosition]);

  useEffect(() => {
    const stopDrag = () => {
      launcherDragOffset.current.dragging = false;
    };

    const moveDrag = (event) => {
      if (launcherDragOffset.current.dragging) {
        setLauncherPosition({
          x: Math.max(16, event.clientX - launcherDragOffset.current.x),
          y: Math.max(16, event.clientY - launcherDragOffset.current.y),
        });
      }
    };

    window.addEventListener('pointermove', moveDrag);
    window.addEventListener('pointerup', stopDrag);
    window.addEventListener('pointercancel', stopDrag);

    return () => {
      window.removeEventListener('pointermove', moveDrag);
      window.removeEventListener('pointerup', stopDrag);
      window.removeEventListener('pointercancel', stopDrag);
    };
  }, []);

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

  useEffect(() => {
    try {
      window.localStorage.setItem('astra.spatialMode', spatialMode ? '1' : '0');
    } catch {
      // Ignore storage failures in restricted browsers.
    }
  }, [spatialMode]);

  // ── Global Gesture Integration ──────────────────────────────────────────
  useEffect(() => {
    // Ensure gesture engine is actively running in the background for global OS bounds
    // Delay by 1.5s to ensure the browser has fully released the webcam hardware handle from LoginScreen
    const startTimeout = setTimeout(() => {
      fetch(`${apiBase}/api/gesture/start`, {
        method: 'POST',
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' }
      }).catch(() => {});
    }, 1500);

    const wsUrl = buildWsUrl(apiBase, '/ws/gestures');
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'gesture') {
        const gesture = msg.data.gesture;
        setLastGesture(gesture);

        // Global Gesture Logic
        if (gesture === 'CLOSED_FIST' || gesture === 'GESTURE_FIST') {
          raiseOverlay('launcher');
          setIsLauncherOpen(prev => !prev);
        } else if (gesture === 'SWIPE_RIGHT' || gesture === 'GESTURE_SWIPE_RIGHT') {
          const nextMap = { terminal: 'os', os: 'filesystem', filesystem: 'analytics', analytics: 'terminal' };
          setActivePanel(prev => nextMap[prev] || 'terminal');
        } else if (gesture === 'SWIPE_LEFT' || gesture === 'GESTURE_SWIPE_LEFT') {
          const prevMap = { terminal: 'analytics', analytics: 'filesystem', filesystem: 'os', os: 'terminal' };
          setActivePanel(prev => prevMap[prev] || 'terminal');
        } else if ((gesture === 'OPEN_PALM' || gesture === 'GESTURE_OPEN_PALM') && window.JARVIS_DESKTOP) {
          window.JARVIS_DESKTOP.windowControl('minimize');
        }
      }
    };

    return () => {
      clearTimeout(startTimeout);
      ws.close();
    };
  }, [apiBase, token]);

  return (
    <div className={`h-screen flex flex-col overflow-hidden ${biosMode ? 'bios-mode' : ''} ${isDesktop ? 'pt-8' : ''}`} data-testid="jarvis-dashboard">
      {/* Electron Draggable Titlebar */}
      {isDesktop && (
        <div className="absolute top-0 left-0 right-0 h-8 z-[1000] flex items-center justify-between px-4 bg-slate-950/90 border-b border-cyan-900/30" 
             style={{ WebkitAppRegion: 'drag' }}>
          <div className="text-[10px] text-cyan-500/50 tracking-[0.2em] font-bold">
            A.S.T.R.A // SPATIAL SHELL v2026.05
          </div>
          <div className="flex gap-2" style={{ WebkitAppRegion: 'no-drag' }}>
            <button 
              onClick={() => window.JARVIS_DESKTOP.windowControl('minimize')}
              className="text-slate-500 hover:text-cyan-400 transition-colors p-1"
              title="Minimize"
            >
              <Minus size={14} />
            </button>
            <button 
              onClick={() => window.JARVIS_DESKTOP.windowControl('close')}
              className="text-slate-500 hover:text-red-400 transition-colors p-1"
              title="Close System"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}
      {/* Top Bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-cyan-900/50 bg-slate-950/80 backdrop-blur-xl z-40" data-testid="top-bar">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-lg tracking-tighter uppercase text-cyan-400" style={{ textShadow: '0 0 10px rgba(6,182,212,0.4)' }}>
            A.S.T.R.A
          </h1>
          <span className="w-px h-5 bg-cyan-500/40" />
          <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/50">Agentic Spatial Task Reasoning Architecture</span>
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
            onClick={() => setIsLauncherOpen(true)}
            className="p-2 text-cyan-500/60 hover:text-cyan-400 hover:bg-cyan-500/10 transition-all rounded-sm border border-transparent hover:border-cyan-500/20 mr-2"
            title="Bento Launcher"
          >
            <LayoutGrid size={18} />
          </button>
          <button
            type="button"
            onClick={() => setBiosMode((prev) => !prev)}
            className={`px-3 py-1 border text-[10px] font-display tracking-[0.25em] uppercase transition-all ${
              biosMode ? 'border-fuchsia-400/60 text-fuchsia-300 bg-fuchsia-950/40' : 'border-cyan-900/40 text-cyan-300/60 hover:text-cyan-100'
            }`}
          >
            BIOS MODE
          </button>
          <button
            type="button"
            onClick={() => setSpatialMode((prev) => !prev)}
            className={`px-3 py-1 border text-[10px] font-display tracking-[0.25em] uppercase transition-all ${
              spatialMode ? 'border-cyan-400/60 text-cyan-100 bg-cyan-950/50' : 'border-cyan-900/40 text-cyan-300/60 hover:text-cyan-100'
            }`}
            title="Toggle spatial depth mode"
          >
            Spatial Accent
          </button>
          <Clock />
        </div>
      </header>

      {/* Main Grid */}
      <main
        className={`flex-1 grid grid-cols-12 gap-3 p-3 overflow-hidden ${spatialMode ? 'spatial-mode' : ''}`}
        data-spatial-mode={spatialMode ? 'enabled' : 'disabled'}
        data-active-panel={activePanel}
        data-focused-zone={focusedZone}
      >
        {/* Left Column - 3 cols */}
        <div
          className="col-span-3 flex flex-col gap-3 overflow-y-auto spatial-column spatial-column-left"
          data-spatial-role="left"
          data-panel-zone="left"
          onMouseDown={() => setFocusedZone('left')}
        >
          <CalendarWidget />
          <SystemDiagnostics metrics={metrics} />
        </div>

        {/* Center Column - 6 cols */}
        <div
          className="col-span-6 flex flex-col gap-3 overflow-hidden spatial-column spatial-column-center"
          data-spatial-role="center"
          data-panel-zone="center"
          onMouseDown={() => setFocusedZone('center')}
        >
            <CenterWorkspace
              apiBase={apiBase}
              token={token}
              activePanel={activePanel}
              setActivePanel={setActivePanel}
              preferences={preferences}
              onPreferencesChange={onPreferencesChange}
            />
        </div>

        {/* Right Column - 3 cols */}
        <div
          className="col-span-3 flex flex-col gap-3 overflow-y-auto spatial-column spatial-column-right"
          data-spatial-role="right"
          data-panel-zone="right"
          onMouseDown={() => setFocusedZone('right')}
        >
          <WeatherWidget weather={weather} />
          <StatusPanel status={status} />
          <OrchestrationQueuePanel api={apiBase} token={token} />
          <NeuralInsights api={apiBase} token={token} />
        </div>
      </main>

      {/* Bottom Dock */}
      <BottomDock activePanel={activePanel} setActivePanel={setActivePanel} onLogout={onLogout} />

      <NotificationHUD api={apiBase} token={token} lastGesture={lastGesture} />
      <SpatialCursor api={apiBase} scope={activePanel} />
      <BentoLauncher 
        isOpen={isLauncherOpen} 
        onClose={() => setIsLauncherOpen(false)} 
        onLaunch={(id) => setActivePanel(id)} 
        position={launcherPosition}
        onPositionChange={setLauncherPosition}
        onFocus={() => raiseOverlay('launcher')}
        zIndex={overlayZ.launcher}
      />
    </div>
  );
}

function CenterWorkspace({ apiBase, token, activePanel, setActivePanel, preferences, onPreferencesChange, onDetach, floating = false }) {
  return (
    <div className={`flex h-full flex-col overflow-hidden border border-cyan-900/50 bg-slate-950/80 ${floating ? '' : ''}`}>
      <div className="flex items-center justify-between border-b border-cyan-900/50 px-3 py-2">
        <div className="flex items-center gap-2">
          <ArcReactor />
          <span className="font-display text-[10px] uppercase tracking-[0.25em] text-cyan-300/60">Core Workspace</span>
        </div>
        <div />
      </div>

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
          onClick={() => setActivePanel('gesture')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-display tracking-wider uppercase transition-all ${
            activePanel === 'gesture' ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400' : 'text-cyan-300/50 hover:text-cyan-300'
          }`}
          data-testid="tab-gesture"
        >
          <Hand size={14} /> Gesture Control
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

      <div className="flex-1 overflow-hidden" data-spatial-scope={activePanel}>
        {activePanel === 'control' && <SystemControlHUD api={apiBase} token={token} />}
        {activePanel === 'terminal' && <Terminal api={apiBase} token={token} />}
        {activePanel === 'filesystem' && <FilesystemExplorer api={apiBase} token={token} />}
        {activePanel === 'analytics' && <VoiceAnalyticsPanel api={apiBase} token={token} />}
        {activePanel === 'developer' && <DevWorkspace api={apiBase} token={token} />}
        {activePanel === 'gesture' && <GestureControlPanel api={apiBase} token={token} />}
        {activePanel === 'settings' && <SettingsPanel api={apiBase} token={token} preferences={preferences} onPreferencesChange={onPreferencesChange} />}
      </div>
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
