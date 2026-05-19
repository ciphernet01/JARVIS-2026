import React, { useState, useEffect, useCallback } from 'react';
import { Volume2, VolumeX, Sun, Battery, Cpu, Database, Zap, Activity, ShieldAlert } from 'lucide-react';

export default function SystemControlHUD({ api, token }) {
  const [audio, setAudio] = useState({ volume: 50, muted: false });
  const [display, setDisplay] = useState({ brightness: 50 });
  const [power, setPower] = useState({ percent: 100, power_plugged: true });
  const [hw, setHw] = useState({ metrics: { cpu_percent: 0, memory_percent: 0, disk_percent: 0 } });
  const [loading, setLoading] = useState(false);
  
  const headers = { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' };

  // ── Fetch Status ──────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const respA = await fetch(`${api}/api/system/audio`, { headers });
      const respD = await fetch(`${api}/api/system/display`, { headers });
      const respP = await fetch(`${api}/api/system/power`, { headers });
      const respH = await fetch(`${api}/api/system/hardware`, { headers });

      if (respA.ok) setAudio(await respA.json());
      if (respD.ok) setDisplay(await respD.json());
      if (respP.ok) setPower(await respP.json());
      if (respH.ok) setHw(await respH.json());
    } catch (e) {
      console.error("Failed to fetch system status", e);
    }
  }, [api, token]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // ── Actions ────────────────────────────────────────────────
  const setVolume = async (level) => {
    setAudio(prev => ({ ...prev, volume: level }));
    await fetch(`${api}/api/system/audio`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ level })
    });
  };

  const toggleMute = async () => {
    const resp = await fetch(`${api}/api/system/audio/mute`, { method: 'POST', headers });
    if (resp.ok) {
      const data = await resp.json();
      setAudio(prev => ({ ...prev, muted: data.muted }));
    }
  };

  const setBrightness = async (level) => {
    setDisplay(prev => ({ ...prev, brightness: level }));
    await fetch(`${api}/api/system/display`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ level })
    });
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 h-full overflow-y-auto bg-slate-950/20" data-testid="system-control-hud">
      {/* ── Audio Control ── */}
      <section className="border border-cyan-900/40 bg-black/40 p-4 flex flex-col gap-4 group hover:border-cyan-500/30 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Volume2 size={16} className="text-cyan-400" />
            <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Audio Output</span>
          </div>
          <button 
            onClick={toggleMute}
            className={`p-1.5 border ${audio.muted ? 'border-red-500/50 text-red-500 bg-red-950/20' : 'border-cyan-900/50 text-cyan-500'} hover:scale-110 transition-all`}
          >
            {audio.muted ? <VolumeX size={14} /> : <Volume2 size={14} />}
          </button>
        </div>
        
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between font-mono text-[9px] text-cyan-400/50">
            <span>VOLUME</span>
            <span>{audio.volume}%</span>
          </div>
          <input 
            type="range" 
            min="0" max="100" 
            value={audio.volume} 
            onChange={(e) => setVolume(parseInt(e.target.value))}
            className="w-full h-1.5 bg-cyan-950 rounded-none appearance-none cursor-pointer accent-cyan-400"
          />
        </div>
      </section>

      {/* ── Display Control ── */}
      <section className="border border-cyan-900/40 bg-black/40 p-4 flex flex-col gap-4 group hover:border-cyan-500/30 transition-all">
        <div className="flex items-center gap-2">
          <Sun size={16} className="text-amber-400" />
          <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Visual Calibration</span>
        </div>
        
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between font-mono text-[9px] text-cyan-400/50">
            <span>BRIGHTNESS</span>
            <span>{display.brightness}%</span>
          </div>
          <input 
            type="range" 
            min="0" max="100" 
            value={display.brightness} 
            onChange={(e) => setBrightness(parseInt(e.target.value))}
            className="w-full h-1.5 bg-cyan-950 rounded-none appearance-none cursor-pointer accent-amber-400"
          />
        </div>
      </section>

      {/* ── Power Node ── */}
      <section className="border border-cyan-900/40 bg-black/40 p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Battery size={16} className={power.power_plugged ? 'text-green-400' : 'text-amber-400'} />
          <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Power Distribution</span>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="relative w-16 h-16 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="2" fill="transparent" className="text-cyan-950" />
              <circle cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="2" fill="transparent" 
                strokeDasharray={176} 
                strokeDashoffset={176 - (176 * power.percent) / 100}
                className={power.percent < 20 ? 'text-red-500' : 'text-cyan-400'} 
              />
            </svg>
            <span className="absolute font-mono text-xs font-bold text-cyan-100">{power.percent}%</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[9px] text-cyan-400/60 uppercase">Source: {power.power_plugged ? 'A/C POWER' : 'BATTERY CELL'}</span>
            <span className="font-mono text-[9px] text-cyan-300/30">STATUS: {power.power_plugged ? 'CHARGING' : 'DISCHARGING'}</span>
          </div>
        </div>
      </section>

      {/* ── Hardware Pulse ── */}
      <section className="border border-cyan-900/40 bg-black/40 p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-cyan-400" />
          <span className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-300/70">Neural Core Load</span>
        </div>
        
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'CPU', val: hw.metrics.cpu_percent, icon: Cpu },
            { label: 'RAM', val: hw.metrics.memory_percent, icon: Zap },
            { label: 'DSK', val: hw.metrics.disk_percent, icon: Database },
          ].map(({ label, val, icon: Icon }) => (
            <div key={label} className="flex flex-col items-center gap-1.5 p-2 bg-cyan-950/20 border border-cyan-900/20">
              <Icon size={12} className="text-cyan-400/40" />
              <span className="font-mono text-[11px] font-bold text-cyan-100">{Math.round(val)}%</span>
              <span className="font-display text-[8px] tracking-widest text-cyan-500/40">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Security / Identity ── */}
      <section className="col-span-full border border-red-900/30 bg-red-950/10 p-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldAlert size={16} className="text-red-500 animate-pulse" />
          <div className="flex flex-col">
            <span className="font-display text-[9px] tracking-[0.2em] uppercase text-red-400/80">System Integrity: Nominal</span>
            <span className="font-mono text-[8px] text-red-500/40">Secure encryption layer active. No intrusions detected in last 24h.</span>
          </div>
        </div>
        <div className="px-3 py-1 border border-red-900/50 bg-red-950/30 text-red-400 text-[9px] font-display tracking-widest uppercase cursor-not-allowed opacity-50">
          Neural Lockdown
        </div>
      </section>
    </div>
  );
}
