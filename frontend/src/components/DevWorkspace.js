import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Code2, FileCode, Play, List, Plus, Trash2, CheckCircle2 } from 'lucide-react';

export default function DevWorkspace({ api, token }) {
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState('python');
  const [response, setResponse] = useState('');
  const [processing, setProcessing] = useState(false);

  const [mode, setActiveMode] = useState('code'); // 'code' or 'macros'
  const [macros, setMacros] = useState([]);
  const [macroName, setMacroName] = useState('');
  const [macroSteps, setMacroSteps] = useState([]);
  const [newStepValue, setNewStepValue] = useState('');
  const [newStepType, setNewStepType] = useState('command');

  const outputRef = useRef(null);

  const fetchMacros = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/macros/list`, {
        headers: { 'X-JARVIS-TOKEN': token }
      });
      const data = await resp.json();
      if (data.status === 'success') setMacros(data.macros);
    } catch (e) { console.error("Failed to fetch macros", e); }
  }, [api, token]);

  useEffect(() => {
    if (mode === 'macros') fetchMacros();
  }, [mode, fetchMacros]);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [response]);

  const sendCodeRequest = async () => {
    const p = prompt.trim();
    if (!p) return;
    setProcessing(true);
    setResponse('');

    try {
      const resp = await fetch(`${api}/api/code/assist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ prompt: p, language }),
      });
      const data = await resp.json();
      setResponse(data.response || data.error || 'No response');
    } catch (e) {
      setResponse(`Error: ${e.message}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      sendCodeRequest();
    }
  };

  const createMacro = async () => {
    if (!macroName || macroSteps.length === 0) return;
    setProcessing(true);
    try {
      const resp = await fetch(`${api}/api/macros/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ name: macroName, steps: macroSteps }),
      });
      if (resp.ok) {
        setMacroName('');
        setMacroSteps([]);
        fetchMacros();
      }
    } catch (e) { console.error("Macro creation failed", e); }
    finally { setProcessing(false); }
  };

  const executeMacro = async (id) => {
    setProcessing(true);
    setResponse('Starting neural macro execution sequence...');
    try {
      const resp = await fetch(`${api}/api/macros/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ macro_id: id }),
      });
      const data = await resp.json();
      setResponse(JSON.stringify(data.results, null, 2));
    } catch (e) { setResponse(`Macro execution failed: ${e.message}`); }
    finally { setProcessing(false); }
  };

  return (
    <div className="flex flex-col h-full" data-testid="dev-workspace">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-cyan-900/30">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveMode('code')}
            className={`px-3 py-1 text-[9px] font-display uppercase tracking-widest border ${mode === 'code' ? 'border-cyan-400 text-cyan-400 bg-cyan-950/30' : 'border-cyan-900/40 text-cyan-300/40'}`}
          >
            Code
          </button>
          <button
            onClick={() => setActiveMode('macros')}
            className={`px-3 py-1 text-[9px] font-display uppercase tracking-widest border ${mode === 'macros' ? 'border-cyan-400 text-cyan-400 bg-cyan-950/30' : 'border-cyan-900/40 text-cyan-300/40'}`}
          >
            Macros
          </button>
        </div>

        <span className="mx-auto" />

        {mode === 'code' ? (
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="bg-black/60 border border-cyan-900/40 text-cyan-300 text-[10px] font-mono px-2 py-1 focus:outline-none"
          data-testid="language-selector"
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="typescript">TypeScript</option>
          <option value="react">React</option>
          <option value="rust">Rust</option>
          <option value="go">Go</option>
          <option value="html">HTML/CSS</option>
        </select>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden flex">
        {/* Main Panel */}
        <div ref={outputRef} className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed border-r border-cyan-900/20">
          {mode === 'code' ? (
            <>
              {!response && !processing && (
                <div className="text-cyan-900/60 text-center mt-8">
                  <Code2 size={32} className="mx-auto mb-3 text-cyan-900/40" />
                  <p>Developer Mode Active</p>
                  <p className="text-[10px] mt-1">Ask JARVIS to build, debug, or architect code.</p>
                  <p className="text-[10px] mt-0.5">Press Ctrl+Enter to execute</p>
                </div>
              )}
              {processing && (
                <div className="text-cyan-400/60">
                  <span className="animate-typing-cursor">_</span> Generating code...
                </div>
              )}
              {response && (
                <div className="whitespace-pre-wrap text-cyan-100/90">
                  {response}
                </div>
              )}
            </>
          ) : (
            <div className="space-y-6">
              {/* Macro Creator */}
              <div className="border border-cyan-900/30 bg-cyan-950/10 p-4">
                <h4 className="text-cyan-400 text-[10px] uppercase tracking-widest mb-4">Neural Macro Architect</h4>
                <input
                  value={macroName} onChange={e => setMacroName(e.target.value)}
                  placeholder="Macro name (e.g. Start Work)"
                  className="w-full bg-black/40 border border-cyan-900/40 p-2 text-cyan-100 text-[10px] mb-3"
                />

                <div className="flex gap-2 mb-4">
                  <select
                    value={newStepType} onChange={e => setNewStepType(e.target.value)}
                    className="bg-black/40 border border-cyan-900/40 p-2 text-cyan-300 text-[9px] uppercase"
                  >
                    <option value="command">Command</option>
                    <option value="app">App</option>
                    <option value="wait">Wait</option>
                  </select>
                  <input
                    value={newStepValue} onChange={e => setNewStepValue(e.target.value)}
                    placeholder="Value..."
                    className="flex-1 bg-black/40 border border-cyan-900/40 p-2 text-cyan-100 text-[10px]"
                  />
                  <button
                    onClick={() => {
                      if (newStepValue) {
                        setMacroSteps([...macroSteps, { type: newStepType, value: newStepValue }]);
                        setNewStepValue('');
                      }
                    }}
                    className="border border-cyan-500/40 p-2 text-cyan-400"
                  >
                    <Plus size={14} />
                  </button>
                </div>

                <div className="space-y-2 mb-4">
                  {macroSteps.map((s, i) => (
                    <div key={i} className="flex justify-between items-center bg-cyan-900/10 p-2 border border-cyan-900/20">
                      <span className="text-[9px] text-cyan-300/60 uppercase">[{s.type}] {s.value}</span>
                      <button onClick={() => setMacroSteps(macroSteps.filter((_, idx) => idx !== i))} className="text-red-400/50 hover:text-red-400">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>

                <button
                  onClick={createMacro}
                  disabled={processing || !macroName || macroSteps.length === 0}
                  className="w-full border border-green-500/40 text-green-400 py-2 text-[9px] uppercase tracking-widest hover:bg-green-950/20"
                >
                  Authorize Macro
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar for Macros */}
        {mode === 'macros' && (
          <div className="w-64 bg-black/20 p-4 overflow-y-auto">
            <h4 className="text-cyan-300/40 text-[9px] uppercase tracking-widest mb-4">Registered Sequences</h4>
            <div className="space-y-3">
              {macros.map(m => (
                <div key={m.id} className="border border-cyan-900/30 p-3 hover:border-cyan-400 transition-colors group cursor-pointer" onClick={() => executeMacro(m.id)}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-cyan-100 text-[10px] uppercase font-bold">{m.name}</span>
                    <Play size={10} className="text-cyan-400 opacity-0 group-hover:opacity-100" />
                  </div>
                  <div className="text-cyan-300/30 text-[8px]">{m.steps.length} steps programmed</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      {mode === 'code' && (
      <div className="border-t border-cyan-900/30 p-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to build... (Ctrl+Enter to execute)"
          className="w-full bg-black/60 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none resize-none h-20"
          data-testid="dev-input"
          disabled={processing}
        />
        <div className="flex justify-end mt-2">
          <button
            onClick={sendCodeRequest}
            disabled={processing || !prompt.trim()}
            className="flex items-center gap-2 px-4 py-2 border border-cyan-500/40 text-cyan-400 font-display text-[10px] tracking-widest uppercase hover:bg-cyan-950/40 hover:border-cyan-400 disabled:opacity-30 transition-all"
            data-testid="dev-execute-btn"
          >
            <Play size={12} /> Execute
          </button>
        </div>
      </div>
      )}
    </div>
  );
}
