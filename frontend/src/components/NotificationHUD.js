import React, { useState, useEffect } from 'react';
import { AlertCircle, Info, Zap, Shield, Bell, X } from 'lucide-react';

export default function NotificationHUD({ api, token, lastGesture }) {
  const [notifications, setNotifications] = useState([]);
  const [showGestureFeedback, setShowGestureFeedback] = useState(false);

  // Poll for proactive insights to convert to notifications
  useEffect(() => {
    const fetchInsights = async () => {
      try {
        const resp = await fetch(`${api}/api/intelligence/insights`, {
          headers: { 'X-JARVIS-TOKEN': token }
        });
        if (resp.ok) {
          const data = await resp.json();
          // Filter out existing or old insights
          const newInsights = (data.insights || []).map(ins => ({
            id: ins.id,
            title: ins.title,
            text: ins.text,
            type: ins.type === 'suggestion' ? 'ACTION' : 'INFO',
            timestamp: new Date().toLocaleTimeString()
          }));
          if (newInsights.length > 0) {
            setNotifications(prev => {
              const ids = new Set(prev.map(n => n.id));
              return [...prev, ...newInsights.filter(n => !ids.has(n.id))].slice(-3);
            });
          }
        }
      } catch (e) {
        console.error("Notification polling error:", e);
      }
    };

    const interval = setInterval(fetchInsights, 20000);
    fetchInsights();
    return () => clearInterval(interval);
  }, [api, token]);

  // Show gesture feedback
  useEffect(() => {
    if (lastGesture && lastGesture !== 'GESTURE_NONE') {
      setShowGestureFeedback(true);
      const timer = setTimeout(() => setShowGestureFeedback(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [lastGesture]);

  const removeNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  return (
    <div className="fixed top-20 right-6 z-[90] flex flex-col items-end gap-3 pointer-events-none w-80">
      {/* Gesture Feedback Bubble */}
      {showGestureFeedback && (
        <div className="bg-cyan-500 text-slate-950 px-4 py-2 rounded-full flex items-center gap-2 shadow-lg shadow-cyan-500/20 animate-in slide-in-from-right duration-300">
          <Zap size={14} fill="currentColor" />
          <span className="text-[10px] font-bold uppercase tracking-widest">{lastGesture.replace('GESTURE_', '')} DETECTED</span>
        </div>
      )}

      {/* Notifications */}
      {notifications.map((note) => (
        <div key={note.id} className="pointer-events-auto w-full bg-slate-950/80 backdrop-blur-md border border-cyan-500/30 p-4 shadow-xl border-l-4 border-l-cyan-400 animate-in slide-in-from-right">
          <div className="flex justify-between items-start mb-2">
            <div className="flex items-center gap-2">
              <div className="p-1 px-1.5 bg-cyan-500/20 text-cyan-400 text-[8px] font-bold tracking-tighter uppercase rounded-sm border border-cyan-500/30">
                {note.type}
              </div>
              <span className="text-[8px] text-cyan-900 font-mono italic">{note.timestamp}</span>
            </div>
            <button 
              onClick={() => removeNotification(note.id)}
              className="text-cyan-900 hover:text-cyan-400 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
          <div className="text-xs font-bold text-cyan-100 uppercase tracking-tight mb-1">{note.title}</div>
          <div className="text-[10px] text-cyan-400/70 font-mono leading-relaxed">{note.text}</div>
          
          <div className="mt-3 flex gap-2">
             <button className="flex-1 bg-cyan-500/10 border border-cyan-500/30 text-[9px] text-cyan-400 py-1 uppercase tracking-tighter hover:bg-cyan-500 hover:text-slate-950 transition-all">Dismiss</button>
             {note.type === 'ACTION' && (
               <button className="flex-1 bg-cyan-500 text-slate-950 text-[9px] font-bold py-1 uppercase tracking-tighter hover:bg-white transition-all">Authorize</button>
             )}
          </div>
        </div>
      ))}
    </div>
  );
}
