import React from 'react';

export default function ArcReactor() {
  return (
    <div className="relative w-40 h-40" data-testid="arc-reactor">
      {/* Outer spinning ring */}
      <svg viewBox="0 0 200 200" className="absolute inset-0 w-full h-full animate-reactor-spin">
        <circle cx="100" cy="100" r="95" fill="none" stroke="rgba(6,182,212,0.12)" strokeWidth="1" />
        <circle cx="100" cy="100" r="95" fill="none" stroke="rgba(6,182,212,0.35)" strokeWidth="1.5"
          strokeDasharray="8 12" strokeLinecap="round" />
        <circle cx="100" cy="100" r="85" fill="none" stroke="rgba(6,182,212,0.08)" strokeWidth="1" />
        <circle cx="100" cy="100" r="85" fill="none" stroke="rgba(6,182,212,0.25)" strokeWidth="1"
          strokeDasharray="20 8 4 8" />
        {/* Arc segments */}
        <path d="M 100 8 A 92 92 0 0 1 180 55" fill="none" stroke="rgba(6,182,212,0.4)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M 190 100 A 92 92 0 0 1 145 180" fill="none" stroke="rgba(6,182,212,0.3)" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M 55 188 A 92 92 0 0 1 8 100" fill="none" stroke="rgba(6,182,212,0.35)" strokeWidth="2" strokeLinecap="round" />
        {/* Tick marks */}
        <line x1="100" y1="3" x2="100" y2="12" stroke="rgba(6,182,212,0.3)" strokeWidth="1" />
        <line x1="197" y1="100" x2="188" y2="100" stroke="rgba(6,182,212,0.3)" strokeWidth="1" />
        <line x1="100" y1="197" x2="100" y2="188" stroke="rgba(6,182,212,0.3)" strokeWidth="1" />
        <line x1="3" y1="100" x2="12" y2="100" stroke="rgba(6,182,212,0.3)" strokeWidth="1" />
        {/* Dots */}
        <circle cx="100" cy="5" r="2.5" fill="rgba(6,182,212,0.6)" />
        <circle cx="195" cy="100" r="2" fill="rgba(6,182,212,0.5)" />
        <circle cx="100" cy="195" r="2" fill="rgba(6,182,212,0.4)" />
        <circle cx="5" cy="100" r="2" fill="rgba(6,182,212,0.5)" />
      </svg>

      {/* Inner counter-spin ring */}
      <div className="absolute inset-6 border border-cyan-500/25 rounded-full animate-reactor-counter" />
      <div className="absolute inset-10 border border-cyan-500/15 rounded-full" />

      {/* Core glow */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="w-16 h-16 rounded-full animate-pulse-glow" style={{
          background: 'radial-gradient(circle, rgba(6,182,212,0.3) 0%, transparent 70%)',
        }} />
      </div>

      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
        <span className="font-display text-[9px] tracking-[0.2em] text-cyan-400/80 uppercase">Core</span>
        <span className="font-display text-[8px] tracking-[0.15em] text-cyan-300/50 uppercase">Active</span>
      </div>
    </div>
  );
}
