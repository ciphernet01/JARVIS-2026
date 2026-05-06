import React, { useState, useRef, useEffect } from 'react';
import { Send, Code2, FileCode, Play } from 'lucide-react';

export default function DevWorkspace({ api, token }) {
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState('python');
  const [response, setResponse] = useState('');
  const [processing, setProcessing] = useState(false);
  const outputRef = useRef(null);

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

  return (
    <div className="flex flex-col h-full" data-testid="dev-workspace">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-cyan-900/30">
        <Code2 size={14} className="text-cyan-400" />
        <span className="font-display text-[9px] tracking-widest text-cyan-300/50 uppercase">Developer Mode</span>
        <span className="mx-auto" />
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

      {/* Output */}
      <div ref={outputRef} className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed" data-testid="dev-output">
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
      </div>

      {/* Input */}
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
    </div>
  );
}
