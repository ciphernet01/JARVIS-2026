import React from 'react';
import { Activity, Database, Cpu, Zap, Clock } from 'lucide-react';

export default function StatusPanel({ status }) {
  if (!status) {
    return (
      <div className="border border-cyan-900/50 p-4" data-testid="status-panel">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">System Status</h3>
        <div className="text-cyan-900 text-xs font-mono">Initializing...</div>
      </div>
    );
  }

  const formatUptime = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}h ${m}m ${s}s`;
  };

  const rows = [
    { label: 'LLM Provider', value: status.llm_provider || 'N/A', online: status.llm_available },
    { label: 'Conversations', value: String(status.conversation_count || 0) },
    { label: 'Platform', value: status.platform || 'N/A' },
    { label: 'Uptime', value: formatUptime(status.uptime_seconds || 0) },
    { label: 'Skills', value: String((status.skills || []).length) },
  ];

  return (
    <div className="border border-cyan-900/50 p-4 flex-1" data-testid="status-panel">
      <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">System Status</h3>
      <div className="space-y-2">
        {rows.map((row, i) => (
          <div key={i} className="flex items-center justify-between py-1.5 px-2 border border-cyan-900/20">
            <span className="font-mono text-[10px] text-cyan-300/50">{row.label}</span>
            <span className={`font-mono text-[10px] ${row.online !== undefined ? (row.online ? 'text-green-400' : 'text-red-400') : 'text-cyan-100'}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
