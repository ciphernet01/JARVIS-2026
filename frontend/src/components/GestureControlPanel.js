import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Hand, Play, Square, RefreshCw, Activity, Eye, Sliders, ChevronRight } from 'lucide-react';

const GESTURE_ICONS = {
  open_palm: '🖐️',
  fist: '✊',
  pointing: '👆',
  thumbs_up: '👍',
  thumbs_down: '👎',
  peace: '✌️',
  swipe_left: '👈',
  swipe_right: '👉',
  none: '—',
};

const GESTURE_LABELS = {
  open_palm: 'OPEN PALM',
  fist: 'FIST',
  pointing: 'POINTING',
  thumbs_up: 'THUMBS UP',
  thumbs_down: 'THUMBS DOWN',
  peace: 'PEACE',
  swipe_left: 'SWIPE LEFT',
  swipe_right: 'SWIPE RIGHT',
  none: 'NO GESTURE',
};

export default function GestureControlPanel({ api, token }) {
  const [gestureState, setGestureState] = useState(null);
  const [frame, setFrame] = useState(null);
  const [events, setEvents] = useState([]);
  const [actionMap, setActionMap] = useState({});
  const [capabilities, setCapabilities] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('live');
  const pollRef = useRef(null);
  const headers = { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' };

  // ── Fetch helpers ──────────────────────────────────────────
  const fetchState = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/gesture/state`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setGestureState(data);
        setError(null);
      }
    } catch (e) {
      setError('Connection lost');
    }
  }, [api, token]);

  const fetchFrame = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/gesture/frame`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setFrame(data.frame);
        setGestureState(prev => ({
          ...prev,
          gesture: data.gesture,
          confidence: data.confidence,
          hand_count: data.hand_count,
        }));
      }
    } catch { /* non-critical */ }
  }, [api, token]);

  const fetchEvents = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/gesture/events?limit=15`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setEvents(data.events || []);
      }
    } catch { /* non-critical */ }
  }, [api, token]);

  const fetchActions = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/gesture/actions`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setActionMap(data.action_map || {});
      }
    } catch { /* non-critical */ }
  }, [api, token]);

  const fetchCapabilities = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/gesture/capabilities`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setCapabilities(data);
      }
    } catch { /* non-critical */ }
  }, [api, token]);

  // ── Actions ────────────────────────────────────────────────
  const startRecognition = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${api}/api/gesture/start`, { method: 'POST', headers });
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === 'started' || data.status === 'already_active') {
          startPolling();
        }
        fetchState();
      }
    } catch (e) {
      setError('Failed to start recognition');
    } finally {
      setLoading(false);
    }
  };

  const stopRecognition = async () => {
    setLoading(true);
    try {
      await fetch(`${api}/api/gesture/stop`, { method: 'POST', headers });
      stopPolling();
      setFrame(null);
      fetchState();
    } catch (e) {
      setError('Failed to stop recognition');
    } finally {
      setLoading(false);
    }
  };

  const resetActions = async () => {
    try {
      await fetch(`${api}/api/gesture/actions/reset`, { method: 'POST', headers });
      fetchActions();
    } catch { /* non-critical */ }
  };

  // ── Polling ────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(() => {
      fetchFrame();
      fetchEvents();
    }, 100); // ~10 fps polling
  }, [fetchFrame, fetchEvents]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // ── Lifecycle ──────────────────────────────────────────────
  useEffect(() => {
    fetchState();
    fetchActions();
    fetchCapabilities();
    return () => stopPolling();
  }, []);

  useEffect(() => {
    if (gestureState?.active) {
      startPolling();
    }
    return () => stopPolling();
  }, [gestureState?.active]);

  const isActive = gestureState?.active || false;
  const isAvailable = gestureState?.available ?? capabilities?.available ?? false;
  const currentGesture = gestureState?.gesture || 'none';
  const confidence = gestureState?.confidence || 0;
  const handCount = gestureState?.hand_count || 0;

  return (
    <div className="flex flex-col h-full overflow-hidden" data-testid="gesture-control-panel">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-900/50">
        <div className="flex items-center gap-3">
          <Hand size={16} className="text-cyan-400" />
          <span className="font-display text-[10px] tracking-[0.25em] uppercase text-cyan-300/70">
            Gesture Control Interface
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-green-400 animate-pulse' : isAvailable ? 'bg-amber-400' : 'bg-red-400'}`} />
          <span className="font-mono text-[9px] tracking-widest text-cyan-300/50 uppercase">
            {isActive ? 'TRACKING' : isAvailable ? 'STANDBY' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex border-b border-cyan-900/30">
        {[
          { key: 'live', label: 'Live Feed', icon: Eye },
          { key: 'actions', label: 'Action Map', icon: Sliders },
          { key: 'log', label: 'Event Log', icon: Activity },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-display tracking-wider uppercase transition-all ${
              activeTab === key
                ? 'text-cyan-400 bg-cyan-950/40 border-b border-cyan-400'
                : 'text-cyan-300/40 hover:text-cyan-300/70'
            }`}
            data-testid={`gesture-tab-${key}`}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {error && (
          <div className="mb-3 px-3 py-2 border border-red-500/30 bg-red-950/20 text-red-400 text-[10px] font-mono tracking-wide">
            ⚠ {error}
          </div>
        )}

        {activeTab === 'live' && (
          <LiveFeedTab
            isActive={isActive}
            isAvailable={isAvailable}
            frame={frame}
            currentGesture={currentGesture}
            confidence={confidence}
            handCount={handCount}
            loading={loading}
            actionMap={actionMap}
            onStart={startRecognition}
            onStop={stopRecognition}
          />
        )}

        {activeTab === 'actions' && (
          <ActionMapTab
            actionMap={actionMap}
            onReset={resetActions}
          />
        )}

        {activeTab === 'log' && (
          <EventLogTab events={events} />
        )}
      </div>
    </div>
  );
}


/* ────────────────────────────────────────────────────────────
   Live Feed Tab
   ──────────────────────────────────────────────────────────── */
function LiveFeedTab({ isActive, isAvailable, frame, currentGesture, confidence, handCount, loading, actionMap, onStart, onStop }) {
  return (
    <div className="flex flex-col gap-3">
      {/* Webcam Feed Area */}
      <div className="relative border border-cyan-900/50 bg-black/60 overflow-hidden" style={{ minHeight: 320 }}>
        {isActive && frame ? (
          <>
            <img
              src={`data:image/jpeg;base64,${frame}`}
              alt="Gesture Feed"
              className="w-full h-full object-contain"
              style={{ maxHeight: 360, imageRendering: 'auto' }}
              data-testid="gesture-feed-image"
            />
            {/* HUD Overlay */}
            <div className="absolute inset-0 pointer-events-none">
              {/* Corner brackets */}
              <div className="absolute top-2 left-2 w-6 h-6 border-l-2 border-t-2 border-cyan-400/60" />
              <div className="absolute top-2 right-2 w-6 h-6 border-r-2 border-t-2 border-cyan-400/60" />
              <div className="absolute bottom-2 left-2 w-6 h-6 border-l-2 border-b-2 border-cyan-400/60" />
              <div className="absolute bottom-2 right-2 w-6 h-6 border-r-2 border-b-2 border-cyan-400/60" />
              {/* Scan line */}
              <div className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent animate-scan" />
              {/* REC indicator */}
              <div className="absolute top-3 right-10 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="font-mono text-[9px] text-red-400 tracking-widest">REC</span>
              </div>
              {/* FPS */}
              <div className="absolute bottom-3 left-3">
                <span className="font-mono text-[9px] text-cyan-400/50">15 FPS</span>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-80 gap-4">
            <div className="relative">
              <Hand size={48} className="text-cyan-400/20" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-12 h-12 border border-cyan-400/10 rounded-full animate-ping" style={{ animationDuration: '3s' }} />
              </div>
            </div>
            <span className="font-display text-[10px] tracking-[0.3em] uppercase text-cyan-300/30">
              {!isAvailable ? 'MEDIAPIPE UNAVAILABLE' : 'GESTURE FEED INACTIVE'}
            </span>
            {!isAvailable && (
              <span className="font-mono text-[9px] text-amber-400/50">
                Install mediapipe + opencv to enable gesture control
              </span>
            )}
          </div>
        )}
      </div>

      {/* Gesture Status Bar */}
      <div className="grid grid-cols-3 gap-2">
        {/* Current Gesture */}
        <div className="border border-cyan-900/50 bg-slate-950/80 p-3 flex flex-col items-center gap-1">
          <span className="font-display text-[8px] tracking-[0.3em] uppercase text-cyan-300/40">Gesture</span>
          <span className="text-2xl">{GESTURE_ICONS[currentGesture] || '—'}</span>
          <span className={`font-mono text-[10px] tracking-wider ${currentGesture !== 'none' ? 'text-cyan-300' : 'text-cyan-300/30'}`}>
            {GESTURE_LABELS[currentGesture] || 'NONE'}
          </span>
        </div>

        {/* Confidence */}
        <div className="border border-cyan-900/50 bg-slate-950/80 p-3 flex flex-col items-center gap-1">
          <span className="font-display text-[8px] tracking-[0.3em] uppercase text-cyan-300/40">Confidence</span>
          <span className={`font-mono text-xl font-bold ${confidence > 0.8 ? 'text-green-400' : confidence > 0.5 ? 'text-amber-400' : 'text-cyan-300/30'}`}>
            {isActive ? `${Math.round(confidence * 100)}%` : '—'}
          </span>
          <div className="w-full h-1.5 bg-cyan-950/50 border border-cyan-900/30 overflow-hidden">
            <div
              className="h-full transition-all duration-200"
              style={{
                width: `${confidence * 100}%`,
                background: confidence > 0.8
                  ? 'linear-gradient(90deg, #22d3ee, #34d399)'
                  : confidence > 0.5
                    ? 'linear-gradient(90deg, #f59e0b, #eab308)'
                    : 'rgba(6, 182, 212, 0.3)',
                boxShadow: confidence > 0.8 ? '0 0 8px rgba(34, 211, 153, 0.4)' : 'none',
              }}
            />
          </div>
        </div>

        {/* Hands Detected */}
        <div className="border border-cyan-900/50 bg-slate-950/80 p-3 flex flex-col items-center gap-1">
          <span className="font-display text-[8px] tracking-[0.3em] uppercase text-cyan-300/40">Hands</span>
          <span className={`font-mono text-xl font-bold ${handCount > 0 ? 'text-cyan-300' : 'text-cyan-300/30'}`}>
            {isActive ? handCount : '—'}
          </span>
          <span className="font-mono text-[9px] text-cyan-300/30">
            {handCount > 0 ? 'DETECTED' : 'SCANNING'}
          </span>
        </div>
      </div>

      {/* Mapped Action Display */}
      {isActive && currentGesture !== 'none' && actionMap[currentGesture] && (
        <div className="border border-cyan-500/30 bg-cyan-950/20 px-3 py-2 flex items-center gap-2 gesture-action-pulse">
          <ChevronRight size={12} className="text-cyan-400" />
          <span className="font-display text-[9px] tracking-[0.2em] uppercase text-cyan-300/60">ACTION:</span>
          <span className="font-mono text-[11px] text-cyan-200">{actionMap[currentGesture]?.label || actionMap[currentGesture]?.action}</span>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex gap-2">
        {!isActive ? (
          <button
            onClick={onStart}
            disabled={loading || !isAvailable}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 border border-green-500/40 bg-green-950/20 text-green-400 text-[10px] font-display tracking-[0.2em] uppercase hover:bg-green-950/40 hover:border-green-400 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            data-testid="gesture-start-btn"
          >
            <Play size={14} />
            {loading ? 'INITIALIZING...' : 'START RECOGNITION'}
          </button>
        ) : (
          <button
            onClick={onStop}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 border border-red-500/40 bg-red-950/20 text-red-400 text-[10px] font-display tracking-[0.2em] uppercase hover:bg-red-950/40 hover:border-red-400 transition-all disabled:opacity-30"
            data-testid="gesture-stop-btn"
          >
            <Square size={14} />
            {loading ? 'STOPPING...' : 'STOP RECOGNITION'}
          </button>
        )}
      </div>
    </div>
  );
}


/* ────────────────────────────────────────────────────────────
   Action Map Tab
   ──────────────────────────────────────────────────────────── */
function ActionMapTab({ actionMap, onReset }) {
  const gestures = Object.entries(actionMap);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-display text-[9px] tracking-[0.3em] uppercase text-cyan-300/50">
          Gesture → Action Mapping
        </span>
        <button
          onClick={onReset}
          className="flex items-center gap-1 px-2 py-1 border border-cyan-900/40 text-cyan-300/50 text-[9px] font-display tracking-wider uppercase hover:text-cyan-300 hover:border-cyan-400/40 transition-all"
          data-testid="gesture-reset-actions"
        >
          <RefreshCw size={10} />
          Reset
        </button>
      </div>

      <div className="grid gap-1.5">
        {gestures.map(([gesture, info]) => (
          <div
            key={gesture}
            className="flex items-center gap-3 px-3 py-2 border border-cyan-900/30 bg-slate-950/60 hover:border-cyan-900/50 transition-all group"
          >
            <span className="text-lg w-8 text-center">{GESTURE_ICONS[gesture] || '?'}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-cyan-200">{GESTURE_LABELS[gesture] || gesture}</span>
                <ChevronRight size={10} className="text-cyan-500/30" />
                <span className="font-mono text-[10px] text-amber-400/80">{info.label || info.action}</span>
              </div>
              <span className="font-mono text-[8px] text-cyan-300/30 block truncate">{info.description}</span>
            </div>
          </div>
        ))}
      </div>

      {gestures.length === 0 && (
        <div className="text-center py-8 text-cyan-300/20 font-display text-[10px] tracking-widest uppercase">
          No action mappings configured
        </div>
      )}
    </div>
  );
}


/* ────────────────────────────────────────────────────────────
   Event Log Tab
   ──────────────────────────────────────────────────────────── */
function EventLogTab({ events }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="font-display text-[9px] tracking-[0.3em] uppercase text-cyan-300/50">
        Recent Gesture Events ({events.length})
      </span>

      <div className="flex flex-col gap-1">
        {events.map((event, idx) => {
          const time = new Date(event.timestamp * 1000);
          const timeStr = `${String(time.getHours()).padStart(2, '0')}:${String(time.getMinutes()).padStart(2, '0')}:${String(time.getSeconds()).padStart(2, '0')}`;
          return (
            <div
              key={`${event.timestamp}-${idx}`}
              className="flex items-center gap-3 px-3 py-1.5 border border-cyan-900/20 bg-slate-950/40 hover:border-cyan-900/40 transition-all"
            >
              <span className="font-mono text-[9px] text-cyan-300/30 w-16 shrink-0">{timeStr}</span>
              <span className="text-sm w-6 text-center">{GESTURE_ICONS[event.gesture] || '?'}</span>
              <span className="font-mono text-[10px] text-cyan-200 flex-1">{GESTURE_LABELS[event.gesture] || event.gesture}</span>
              <span className={`font-mono text-[9px] w-10 text-right ${event.confidence > 0.8 ? 'text-green-400' : 'text-amber-400'}`}>
                {Math.round(event.confidence * 100)}%
              </span>
              {event.action && (
                <span className="font-mono text-[8px] text-amber-400/60 px-1.5 py-0.5 border border-amber-500/20 bg-amber-950/20">
                  {event.action}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {events.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Activity size={32} className="text-cyan-400/10" />
          <span className="font-display text-[10px] tracking-[0.3em] uppercase text-cyan-300/20">
            No gesture events recorded
          </span>
          <span className="font-mono text-[9px] text-cyan-300/15">
            Start recognition to begin tracking
          </span>
        </div>
      )}
    </div>
  );
}
