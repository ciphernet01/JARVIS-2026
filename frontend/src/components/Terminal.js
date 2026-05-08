import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';

export default function Terminal({ api, token }) {
  const [messages, setMessages] = useState([
    { type: 'system', text: 'JARVIS Neural Interface Online. All systems nominal.' },
    { type: 'system', text: 'Awaiting commands, Sir.' },
  ]);
  const [input, setInput] = useState('');
  const [processing, setProcessing] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(true);
  const [listening, setListening] = useState(false);
  const outputRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages]);

  // Voice recognition setup
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInput(transcript);
        setListening(false);
      };
      recognition.onend = () => setListening(false);
      recognition.onerror = () => setListening(false);
      recognitionRef.current = recognition;
    }
  }, []);

  const speak = (text) => {
    if (!speechEnabled || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const clean = text.replace(/[*_#`~>]+/g, '').replace(/\[(.*?)\]\(.*?\)/g, '$1');
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = 'en-GB';
    utterance.rate = 1.05;
    utterance.pitch = 0.85;
    const voices = window.speechSynthesis.getVoices();
    const british = voices.find(v => v.name.includes('Google UK English Male')) ||
      voices.find(v => v.lang === 'en-GB') || voices[0];
    if (british) utterance.voice = british;
    window.speechSynthesis.speak(utterance);
  };

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
    } else {
      recognitionRef.current.start();
      setListening(true);
    }
  };

  const sendCommand = async () => {
    const cmd = input.trim();
    if (!cmd) return;
    setInput('');
    setMessages(prev => [...prev, { type: 'user', text: cmd }]);
    setProcessing(true);

    try {
      const resp = await fetch(`${api}/api/operator/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await resp.json();
      if (data.error) {
        setMessages(prev => [...prev, { type: 'error', text: data.error || data.detail }]);
      } else {
        const prefix = data.source === 'operator' || data.handled ? '[OPERATOR] ' : '';
        setMessages(prev => [...prev, { type: 'jarvis', text: `${prefix}${data.response}` }]);
        speak(data.response);
      }
    } catch (e) {
      setMessages(prev => [...prev, { type: 'error', text: `Connection error: ${e.message}` }]);
    } finally {
      setProcessing(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendCommand();
    }
  };

  return (
    <div className="flex flex-col h-full" data-testid="terminal-panel">
      {/* Voice controls */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-cyan-900/30">
        <button
          onClick={toggleListening}
          className={`p-1.5 border rounded-sm transition-all ${listening ? 'border-green-400 text-green-400 bg-green-950/30' : 'border-cyan-900/50 text-cyan-400/60 hover:text-cyan-400'}`}
          data-testid="voice-toggle-btn"
          title={listening ? 'Stop listening' : 'Start voice input'}
        >
          {listening ? <Mic size={14} /> : <MicOff size={14} />}
        </button>
        <button
          onClick={() => setSpeechEnabled(!speechEnabled)}
          className={`p-1.5 border rounded-sm transition-all ${speechEnabled ? 'border-cyan-500/40 text-cyan-400' : 'border-cyan-900/50 text-cyan-400/40'}`}
          data-testid="speech-toggle-btn"
          title={speechEnabled ? 'Disable speech' : 'Enable speech'}
        >
          {speechEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
        </button>
        <span className="ml-auto font-mono text-[10px] text-cyan-300/40 tracking-wider">
          {listening ? '[ LISTENING ]' : processing ? '[ PROCESSING ]' : '[ READY ]'}
        </span>
      </div>

      {/* Output */}
      <div ref={outputRef} className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs leading-relaxed" data-testid="terminal-output">
        {messages.map((msg, i) => (
          <div key={i} className={`${
            msg.type === 'system' ? 'text-cyan-400/70' :
            msg.type === 'user' ? 'text-cyan-100' :
            msg.type === 'jarvis' ? 'text-green-400' :
            'text-red-400'
          }`}>
            <span className="text-cyan-900 mr-2">
              {msg.type === 'user' ? '>' : msg.type === 'jarvis' ? '<' : '#'}
            </span>
            {msg.type === 'jarvis' && <span className="text-green-500/60 mr-1">[JARVIS]</span>}
            <span className="whitespace-pre-wrap">{msg.text}</span>
          </div>
        ))}
        {processing && (
          <div className="text-cyan-400/50">
            <span className="animate-typing-cursor">_</span> Routing command...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 p-3 border-t border-cyan-900/30">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Issue a command..."
          className="flex-1 bg-black/60 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none transition-colors"
          data-testid="terminal-input"
          disabled={processing}
        />
        <button
          onClick={sendCommand}
          disabled={processing || !input.trim()}
          className="px-4 py-2 border border-cyan-500/40 text-cyan-400 font-display text-[10px] tracking-widest uppercase hover:bg-cyan-950/40 hover:border-cyan-400 disabled:opacity-30 transition-all"
          data-testid="terminal-send-btn"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
