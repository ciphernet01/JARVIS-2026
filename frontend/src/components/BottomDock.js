import React from 'react';
import { Terminal, Code2, Activity, Power, Settings, Globe, FolderOpen } from 'lucide-react';

export default function BottomDock({ activePanel, setActivePanel, onLogout }) {
  const items = [
    { id: 'control', icon: Activity, label: 'OS Control' },
    
    { id: 'terminal', icon: Terminal, label: 'Terminal' },
    { id: 'developer', icon: Code2, label: 'Developer' },
    { id: 'filesystem', icon: FolderOpen, label: 'Filesystem' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ];

  const links = [
    { action: () => window.open('https://github.com', '_blank'), icon: Globe, label: 'GitHub' },
  ];

  return (
    <nav className="flex items-center justify-center gap-3 px-6 py-2 border-t border-cyan-900/50 bg-slate-950/90 backdrop-blur-2xl" data-testid="bottom-dock">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => setActivePanel(item.id)}
          className={`flex items-center gap-2 px-3 py-1.5 border text-[10px] font-display tracking-wider uppercase transition-all ${
            activePanel === item.id
              ? 'border-cyan-400 text-cyan-400 bg-cyan-950/30'
              : 'border-cyan-900/40 text-cyan-300/40 hover:text-cyan-300 hover:border-cyan-700'
          }`}
          data-testid={`dock-${item.id}`}
        >
          <item.icon size={12} /> {item.label}
        </button>
      ))}

      <div className="w-px h-5 bg-cyan-900/40 mx-2" />

      {links.map((link, i) => (
        <button
          key={i}
          onClick={link.action}
          className="flex items-center gap-2 px-3 py-1.5 border border-cyan-900/40 text-cyan-300/40 text-[10px] font-display tracking-wider uppercase hover:text-cyan-300 hover:border-cyan-700 transition-all"
          data-testid={`dock-link-${i}`}
        >
          <link.icon size={12} /> {link.label}
        </button>
      ))}

      <div className="w-px h-5 bg-cyan-900/40 mx-2" />

      <button
        onClick={onLogout}
        className="flex items-center gap-2 px-3 py-1.5 border border-red-900/40 text-red-400/60 text-[10px] font-display tracking-wider uppercase hover:text-red-400 hover:border-red-500/60 transition-all"
        data-testid="dock-logout"
      >
        <Power size={12} /> Logout
      </button>
    </nav>
  );
}
