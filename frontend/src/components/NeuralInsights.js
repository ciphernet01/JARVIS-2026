import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, AlertCircle, Info, ChevronRight, Zap, Database } from 'lucide-react';

export default function NeuralInsights({ api, token }) {
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchInsights = async () => {
    try {
      const resp = await fetch(`${api}/api/intelligence/insights`, {
        headers: { 'X-JARVIS-TOKEN': token }
      });
      if (resp.ok) {
        const data = await resp.json();
        setInsights(data.insights || []);
      }
    } catch (e) {
      console.error("Failed to fetch insights:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
    const interval = setInterval(fetchInsights, 15000); // 15s refresh for proactive layer
    return () => clearInterval(interval);
  }, [api, token]);

  if (loading && insights.length === 0) {
    return (
      <div className="border border-cyan-900/50 p-4 bg-slate-950/40 backdrop-blur-md">
        <div className="flex items-center gap-2 mb-3">
          <Brain size={14} className="text-cyan-400 animate-pulse" />
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400">Neural Insights</h3>
        </div>
        <div className="h-20 flex items-center justify-center border border-cyan-900/20">
          <div className="text-[10px] text-cyan-900 animate-pulse font-mono uppercase tracking-widest">Scanning Intents...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-cyan-900/50 p-4 bg-slate-950/40 backdrop-blur-md flex flex-col gap-3 min-h-[160px]" data-testid="neural-insights">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-cyan-400" />
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400">Neural Insights</h3>
        </div>
        {insights.length > 0 && (
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
          </span>
        )}
      </div>

      <div className="flex-1 space-y-3">
        {insights.length === 0 ? (
          <div className="h-full flex items-center justify-center border border-cyan-900/10 py-6 text-center">
             <div className="text-[10px] text-cyan-700 font-mono italic">
               No proactive triggers detected. <br/> System at cognitive equilibrium.
             </div>
          </div>
        ) : (
          insights.map((insight, idx) => (
            <div key={idx} className="group border border-cyan-500/20 bg-cyan-950/10 p-3 transition-all hover:border-cyan-500/50 hover:bg-cyan-950/20 relative overflow-hidden">
               {/* Accent bar */}
               <div className="absolute left-0 top-0 bottom-0 w-1 bg-cyan-500/40" />
               
               <div className="flex items-start gap-2">
                 {insight.type === 'suggestion' ? <Zap size={14} className="text-amber-400 mt-0.5" /> : <Info size={14} className="text-cyan-400 mt-0.5" />}
                 <div className="flex-1">
                    <div className="text-[10px] font-bold text-cyan-100 uppercase tracking-tight mb-0.5">{insight.title}</div>
                    <div className="text-[11px] text-cyan-300/70 leading-relaxed font-mono">{insight.text}</div>
                 </div>
               </div>
               
               {insight.id === 'night_mode' && (
                 <div className="mt-3 flex justify-end">
                    <button className="flex items-center gap-1 px-2 py-1 bg-cyan-500/10 border border-cyan-500/30 text-[9px] text-cyan-400 hover:bg-cyan-500 hover:text-slate-950 transition-all uppercase tracking-tighter">
                      Apply Correction <ChevronRight size={10} />
                    </button>
                 </div>
               )}
            </div>
          ))
        )}
      </div>

      {/* Memory Bank Status */}
      <div className="mt-2 pt-2 border-t border-cyan-900/30 flex items-center justify-between opacity-50">
         <div className="flex items-center gap-1 text-[8px] text-cyan-400 uppercase tracking-widest font-mono">
           <Database size={10} /> Memory Bank: LOCAL_V1
         </div>
         <div className="text-[8px] text-cyan-400 font-mono">SYNC: ACTIVE</div>
      </div>
    </div>
  );
}
