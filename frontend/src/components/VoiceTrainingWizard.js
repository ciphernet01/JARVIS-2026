import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Mic, RefreshCw, RotateCcw, Volume2 } from 'lucide-react';

async function readResponse(resp) {
  const text = await resp.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

export default function VoiceTrainingWizard({ api, token }) {
  const [training, setTraining] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [transcript, setTranscript] = useState('');
  const [confidence, setConfidence] = useState(0.75);
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState(null);
  const recognitionRef = useRef(null);
  const startedAtRef = useRef(null);

  const prompts = training?.prompts || [];
  const activePrompt = prompts[activeIndex] || prompts[0];
  const profile = training?.profile || {};
  const supportsSpeechRecognition = useMemo(() => {
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }, []);

  const refreshTraining = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/voice/training`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Voice training unavailable');
      setTraining(data);
      const nextIndex = (data.prompts || []).findIndex((prompt) => !prompt.completed);
      setActiveIndex(nextIndex >= 0 ? nextIndex : 0);
    } catch (error) {
      setStatus({ success: false, message: `Voice training unavailable: ${error.message}` });
    }
  }, [api, token]);

  useEffect(() => {
    refreshTraining();
    return () => {
      if (recognitionRef.current) recognitionRef.current.stop();
      window.speechSynthesis?.cancel();
    };
  }, [refreshTraining]);

  const speakPrompt = () => {
    if (!activePrompt?.text || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(activePrompt.text);
    utterance.rate = 0.92;
    utterance.pitch = 0.95;
    window.speechSynthesis.speak(utterance);
  };

  const startListening = () => {
    if (!supportsSpeechRecognition || !activePrompt) return;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new Recognition();
    recognition.lang = profile.language || 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;
    startedAtRef.current = Date.now();
    setListening(true);
    setStatus(null);
    recognition.onresult = (event) => {
      const result = event.results?.[0]?.[0];
      setTranscript(result?.transcript || '');
      setConfidence(result?.confidence && result.confidence > 0 ? result.confidence : 0.78);
    };
    recognition.onerror = (event) => {
      setStatus({ success: false, message: `Microphone capture failed: ${event.error || 'unknown error'}` });
    };
    recognition.onend = () => setListening(false);
    recognition.start();
  };

  const savePhrase = async () => {
    if (!activePrompt || !transcript.trim()) return;
    setStatus(null);
    try {
      const duration = startedAtRef.current ? Date.now() - startedAtRef.current : null;
      const resp = await fetch(`${api}/api/os/voice/training/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({
          phrase_id: activePrompt.id,
          prompt: activePrompt.text,
          transcript,
          confidence,
          language: profile.language || 'en-US',
          duration_ms: duration,
        }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Could not save training phrase');
      setTraining(data);
      setTranscript('');
      const nextIndex = (data.prompts || []).findIndex((prompt) => !prompt.completed);
      setActiveIndex(nextIndex >= 0 ? nextIndex : activeIndex);
      setStatus({ success: true, message: 'Voice sample locked into the operator profile.' });
    } catch (error) {
      setStatus({ success: false, message: `Voice sample failed: ${error.message}` });
    }
  };

  const resetTraining = async () => {
    try {
      const resp = await fetch(`${api}/api/os/voice/training/reset`, {
        method: 'POST',
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Reset failed');
      setTraining(data);
      setActiveIndex(0);
      setTranscript('');
      setStatus({ success: true, message: 'Voice training profile reset.' });
    } catch (error) {
      setStatus({ success: false, message: `Reset failed: ${error.message}` });
    }
  };

  return (
    <div className="border border-cyan-900/50 p-4 mb-4">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 flex items-center gap-2">
          <Mic size={14} /> Voice Training
        </h3>
        <div className="font-mono text-[9px] text-cyan-300/45">
          {Math.round((profile.completion_ratio || 0) * 100)}% / {Math.round((profile.average_confidence || 0) * 100)}%
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        {prompts.map((prompt, index) => (
          <button
            key={prompt.id}
            onClick={() => {
              setActiveIndex(index);
              setTranscript('');
            }}
            className={`min-h-12 border px-3 py-2 text-left font-mono text-[9px] transition-all ${
              index === activeIndex
                ? 'border-cyan-400/70 bg-cyan-950/30 text-cyan-100'
                : prompt.completed
                  ? 'border-green-500/30 bg-green-950/10 text-green-300/70'
                  : 'border-cyan-900/30 bg-slate-950/40 text-cyan-300/45'
            }`}
            data-testid={`voice-training-prompt-${index}`}
          >
            <div className="flex items-center gap-2">
              {prompt.completed ? <CheckCircle2 size={11} /> : <span className="text-cyan-500/50">{index + 1}</span>}
              <span>{prompt.text}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="border border-cyan-900/30 bg-slate-950/40 p-3 mb-3">
        <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2">Training Phrase</div>
        <div className="font-mono text-sm text-cyan-100 mb-3">{activePrompt?.text || 'Loading voice prompts...'}</div>
        <div className="grid grid-cols-3 gap-2 mb-3">
          <button
            onClick={speakPrompt}
            disabled={!activePrompt}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="voice-training-speak"
          >
            <Volume2 size={12} /> Speak
          </button>
          <button
            onClick={startListening}
            disabled={!supportsSpeechRecognition || listening || !activePrompt}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-green-500/40 text-green-300 font-display text-[9px] tracking-wider uppercase hover:bg-green-950/20 disabled:opacity-40"
            data-testid="voice-training-record"
          >
            {listening ? <RefreshCw size={12} className="animate-spin" /> : <Mic size={12} />}
            {listening ? 'Listening' : 'Record'}
          </button>
          <button
            onClick={resetTraining}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-amber-500/40 text-amber-300 font-display text-[9px] tracking-wider uppercase hover:bg-amber-950/20"
            data-testid="voice-training-reset"
          >
            <RotateCcw size={12} /> Reset
          </button>
        </div>
        {!supportsSpeechRecognition && (
          <div className="mb-3 font-mono text-[9px] text-amber-300/70">
            Browser speech capture is unavailable here. Type the spoken phrase below to calibrate manually.
          </div>
        )}
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Recognized phrase appears here"
          className="w-full min-h-20 bg-black/50 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none"
          data-testid="voice-training-transcript"
        />
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-3 items-center">
          <input
            type="range"
            min="0.1"
            max="1"
            step="0.01"
            value={confidence}
            onChange={(e) => setConfidence(parseFloat(e.target.value))}
            className="accent-cyan-400"
            data-testid="voice-training-confidence"
          />
          <button
            onClick={savePhrase}
            disabled={!activePrompt || !transcript.trim()}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="voice-training-save"
          >
            <CheckCircle2 size={12} /> Save
          </button>
        </div>
      </div>

      {status && (
        <div className={`flex items-start gap-2 p-3 border ${
          status.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
        }`} data-testid="voice-training-status">
          {status.success ? <CheckCircle2 size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
          <span className="font-mono text-[10px]">{status.message}</span>
        </div>
      )}
    </div>
  );
}
