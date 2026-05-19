import React from 'react';
import { 
  Terminal, 
  Settings, 
  Activity, 
  FolderOpen, 
  ShieldCheck, 
  Database, 
  Cpu, 
  Mic, 
  Camera, 
  Zap,
  LayoutGrid,
  X,
  Play
} from 'lucide-react';

export default function BentoLauncher({ isOpen, onClose, onLaunch }) {
  if (!isOpen) return null;

  const items = [
    { id: 'terminal', icon: <Terminal size={20} />, label: 'Core Terminal', desc: 'System Command Interface' },
    { id: 'settings', icon: <Settings size={20} />, label: 'Neural Settings', desc: 'OS Configuration & Tuning' },
    { id: 'analytics', icon: <Activity size={20} />, label: 'Diagnostics', desc: 'Real-time Performance Metrics' },
    { id: 'filesystem', icon: <FolderOpen size={20} />, label: 'Data Nodes', desc: 'Neural File Explorer' },
    { id: 'security', icon: <ShieldCheck size={20} />, label: 'Bio-Shield', desc: 'Security & Audit Logs' },
    { id: 'memory', icon: <Database size={20} />, label: 'Episodic Store', desc: 'Intelligence Memory Bank' },
    { id: 'hardware', icon: <Cpu size={20} />, label: 'Core Hardware', desc: 'Node & Actuator Control' },
    { id: 'voice', icon: <Mic size={20} />, label: 'Acoustic Link', desc: 'Voice Synthesis & ML' },
    { id: 'gesture', icon: <Zap size={20} />, label: 'Optical HUD', desc: 'Gesture Mapping Engine' },
  ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-xl animate-in fade-in duration-300">
      <div className="max-w-4xl w-full p-8 relative">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 border-b border-cyan-500/20 pb-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/40 rounded-sm">
              <LayoutGrid size={24} className="text-cyan-400" />
            </div>
            <div>
              <h2 className="text-2xl font-display font-bold text-cyan-100 tracking-wider uppercase">Neural Bento Launcher</h2>
              <p className="text-xs text-cyan-500/60 font-mono tracking-widest mt-1">SELECT CORE NODE FOR INITIALIZATION</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-3 text-cyan-500/40 hover:text-cyan-400 hover:bg-cyan-500/10 transition-all border border-transparent hover:border-cyan-500/20"
          >
            <X size={24} />
          </button>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => { onLaunch(item.id); onClose(); }}
              className="group relative flex items-start gap-4 p-5 bg-cyan-950/5 border border-cyan-900/30 hover:border-cyan-400/50 hover:bg-cyan-900/20 transition-all text-left overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <Play size={12} className="text-cyan-400" />
              </div>
              <div className="p-3 bg-cyan-500/5 border border-cyan-500/20 group-hover:border-cyan-400/40 group-hover:bg-cyan-500/10 transition-all">
                <div className="text-cyan-400 group-hover:scale-110 transition-transform">{item.icon}</div>
              </div>
              <div>
                <div className="text-sm font-bold text-cyan-100 uppercase tracking-tight group-hover:text-cyan-400 transition-colors">{item.label}</div>
                <div className="text-[10px] text-cyan-500/60 font-mono mt-1 group-hover:text-cyan-300 transition-colors uppercase tracking-tighter">{item.desc}</div>
              </div>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-8 flex justify-center">
          <div className="text-[10px] text-cyan-900 font-mono flex items-center gap-2 uppercase tracking-[0.3em]">
             <Zap size={10} className="animate-pulse" /> Gesture Control Active: [FIST] to Toggle
          </div>
        </div>
      </div>
    </div>
  );
}
