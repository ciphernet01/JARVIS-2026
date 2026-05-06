import React from 'react';
import { Cpu, HardDrive, MemoryStick } from 'lucide-react';

function GaugeRing({ percent, label, detail, color = '#06b6d4' }) {
  const r = 22;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="relative w-12 h-12 flex-shrink-0">
        <svg viewBox="0 0 52 52" className="w-full h-full" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="26" cy="26" r={r} fill="none" stroke="rgba(6,182,212,0.1)" strokeWidth="3" />
          <circle cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.8s ease', filter: `drop-shadow(0 0 3px ${color})` }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-display text-[9px] font-bold" style={{ color }}>{Math.round(percent)}%</span>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-display text-[9px] tracking-[0.15em] uppercase text-cyan-300/60">{label}</div>
        <div className="font-mono text-[10px] text-cyan-100/50 truncate">{detail}</div>
        <div className="mt-1 h-0.5 bg-cyan-900/30 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all duration-700" style={{ width: `${percent}%`, background: `linear-gradient(90deg, ${color}80, ${color})` }} />
        </div>
      </div>
    </div>
  );
}

export default function SystemDiagnostics({ metrics }) {
  if (!metrics) {
    return (
      <div className="border border-cyan-900/50 p-4 flex-1" data-testid="system-diagnostics">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">System Diagnostics</h3>
        <div className="text-cyan-900 text-xs font-mono">Loading telemetry...</div>
      </div>
    );
  }

  return (
    <div className="border border-cyan-900/50 p-4 flex-1" data-testid="system-diagnostics">
      <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">System Diagnostics</h3>
      <div className="space-y-1">
        <GaugeRing
          percent={metrics.cpu.percent}
          label="CPU"
          detail={`${metrics.cpu.cores} Cores / ${metrics.cpu.freq_mhz} MHz`}
          color="#06b6d4"
        />
        <GaugeRing
          percent={metrics.memory.percent}
          label="Memory"
          detail={`${metrics.memory.used_gb} / ${metrics.memory.total_gb} GB`}
          color="#0ea5e9"
        />
        <GaugeRing
          percent={metrics.disk.percent}
          label="Disk"
          detail={`${metrics.disk.used_gb} / ${metrics.disk.total_gb} GB`}
          color="#8b5cf6"
        />
      </div>

      {/* Network */}
      <div className="mt-3 pt-3 border-t border-cyan-900/30 grid grid-cols-2 gap-2">
        <div>
          <div className="font-display text-[8px] tracking-widest text-cyan-300/40 uppercase">Sent</div>
          <div className="font-mono text-[10px] text-cyan-100/70">{formatBytes(metrics.network.bytes_sent)}</div>
        </div>
        <div>
          <div className="font-display text-[8px] tracking-widest text-cyan-300/40 uppercase">Recv</div>
          <div className="font-mono text-[10px] text-cyan-100/70">{formatBytes(metrics.network.bytes_recv)}</div>
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}
