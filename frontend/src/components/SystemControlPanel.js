import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Cpu, HardDrive, Network, Play, RefreshCw, Search, ShieldCheck, MonitorSmartphone, Camera, Mic, BatteryCharging, Volume2, Wifi, WifiOff, Globe } from 'lucide-react';

function StatCard({ label, value, sublabel, icon: Icon }) {
  return (
    <div className="border border-cyan-900/30 bg-slate-950/60 p-3">
      <div className="flex items-center gap-2 text-cyan-300/50 uppercase tracking-[0.18em] font-display text-[9px] mb-2">
        <Icon size={12} className="text-cyan-400" />
        {label}
      </div>
      <div className="font-mono text-lg text-cyan-100">{value}</div>
      {sublabel && <div className="mt-1 font-mono text-[9px] text-cyan-300/35">{sublabel}</div>}
    </div>
  );
}

export default function SystemControlPanel({ api, token }) {
  const [status, setStatus] = useState(null);
  const [processes, setProcesses] = useState([]);
  const [services, setServices] = useState([]);
  const [devices, setDevices] = useState(null);
  const [command, setCommand] = useState('');
  const [commandResult, setCommandResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [audio, setAudio] = useState(null);
  const [volumeControl, setVolumeControl] = useState(null);
  const [camera, setCamera] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [power, setPower] = useState(null);
  const [powerConfirmation, setPowerConfirmation] = useState(null);
  const [powerActionBusy, setPowerActionBusy] = useState(false);
  const [network, setNetwork] = useState(null);
  const [voice, setVoice] = useState(null);
  const [voiceListening, setVoiceListening] = useState(false);
  const [voiceListenBusy, setVoiceListenBusy] = useState(false);
  const [voiceTranscription, setVoiceTranscription] = useState(null);

  const fetchStatus = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/status`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setStatus(data);
  }, [api, token]);

  const fetchProcesses = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/processes?limit=60`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setProcesses(data.processes || []);
  }, [api, token]);

  const fetchServices = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/services`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setServices(data.services || []);
  }, [api, token]);

  const fetchDevices = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/devices`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setDevices(data);
  }, [api, token]);

  const fetchAudio = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/audio/snapshot`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setAudio(data);
  }, [api, token]);

  const fetchCamera = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/camera/state`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setCamera(data);
  }, [api, token]);

  const fetchPower = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/power/state`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setPower(data);
  }, [api, token]);

  const fetchNetwork = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/network/state`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setNetwork(data);
  }, [api, token]);

  const fetchVoice = useCallback(async () => {
    const resp = await fetch(`${api}/api/os/voice/state`, {
      headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    if (resp.ok) setVoice(data);
  }, [api, token]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([fetchStatus(), fetchProcesses(), fetchServices(), fetchDevices(), fetchAudio(), fetchCamera(), fetchPower(), fetchNetwork(), fetchVoice()]);
    } finally {
      setLoading(false);
    }
  }, [fetchDevices, fetchProcesses, fetchServices, fetchStatus, fetchAudio, fetchCamera, fetchPower, fetchNetwork, fetchVoice]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 5000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const filteredProcesses = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return processes;
    return processes.filter((item) => {
      return [item.name, item.username, item.status, item.cmdline, String(item.pid)]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(q));
    });
  }, [processes, query]);

  const sendCommand = async () => {
    const text = command.trim();
    if (!text) return;
    setBusy(true);
    setCommandResult(null);
    try {
      const resp = await fetch(`${api}/api/os/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ command: text, dry_run: false }),
      });
      const data = await resp.json();
      setCommandResult(data);
      await refreshAll();
    } catch (error) {
      setCommandResult({ handled: false, intent: 'error', response: error.message });
    } finally {
      setBusy(false);
    }
  };

  const handleVolumeChange = async (newVolume) => {
    setVolumeControl(newVolume);
    try {
      const resp = await fetch(`${api}/api/os/audio/volume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ volume: newVolume }),
      });
      if (resp.ok) {
        await fetchAudio();
      }
    } catch (error) {
      console.error('Volume control error:', error);
    }
  };

  const handleMicrophoneToggle = async () => {
    if (!audio) return;
    try {
      const resp = await fetch(`${api}/api/os/audio/microphone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ enabled: !audio.microphone_enabled }),
      });
      if (resp.ok) {
        await fetchAudio();
      }
    } catch (error) {
      console.error('Microphone toggle error:', error);
    }
  };

  const handleCameraEnable = async () => {
    try {
      const resp = await fetch(`${api}/api/os/camera/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
      });
      if (resp.ok) {
        await fetchCamera();
      }
    } catch (error) {
      console.error('Camera enable error:', error);
    }
  };

  const handleCameraDisable = async () => {
    try {
      const resp = await fetch(`${api}/api/os/camera/disable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
      });
      if (resp.ok) {
        await fetchCamera();
      }
    } catch (error) {
      console.error('Camera disable error:', error);
    }
  };

  const handleCaptureSnapshot = async () => {
    if (!camera || !camera.enabled) return;
    setSnapshotBusy(true);
    try {
      const resp = await fetch(`${api}/api/os/camera/snapshot?detect_faces=true`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      if (resp.ok) {
        const data = await resp.json();
        setSnapshot(data);
      }
    } catch (error) {
      console.error('Snapshot capture error:', error);
    } finally {
      setSnapshotBusy(false);
    }
  };

  const handleFaceDetectionToggle = async () => {
    if (!camera) return;
    try {
      const resp = await fetch(`${api}/api/os/camera/face-detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ face_detection: !camera.face_detection_active }),
      });
      if (resp.ok) {
        await fetchCamera();
      }
    } catch (error) {
      console.error('Face detection toggle error:', error);
    }
  };

  const handlePowerAction = async (action) => {
    setPowerConfirmation(null);
    setPowerActionBusy(true);
    try {
      const resp = await fetch(`${api}/api/os/power/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ action, confirmed: true }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setCommandResult({
          handled: true,
          intent: 'power_action',
          response: data.message
        });
        await fetchPower();
      }
    } catch (error) {
      console.error('Power action error:', error);
    } finally {
      setPowerActionBusy(false);
    }
  };

  const handleVoiceListen = async () => {
    setVoiceListenBusy(true);
    setVoiceListening(true);
    try {
      const resp = await fetch(`${api}/api/os/voice/listen`, {
        method: 'POST',
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await resp.json();
      if (resp.ok && data.command) {
        setVoiceTranscription(data.command);
        setCommandResult({
          handled: true,
          intent: 'voice_command',
          response: `Recognized: "${data.command.text}" (confidence: ${Math.round(data.command.confidence * 100)}%)`
        });
      } else {
        setVoiceTranscription(null);
      }
      await fetchVoice();
    } catch (error) {
      console.error('Voice listen error:', error);
      setCommandResult({ handled: false, intent: 'error', response: `Voice error: ${error.message}` });
    } finally {
      setVoiceListening(false);
      setVoiceListenBusy(false);
    }
  };

  const killable = services.filter((service) => service.status === 'running');

  return (
    <div className="flex h-full flex-col overflow-hidden" data-testid="system-control-panel">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-cyan-900/30">
        <ShieldCheck size={14} className="text-cyan-400" />
        <span className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">OS Control Center</span>
        <button
          onClick={refreshAll}
          className="ml-auto flex items-center gap-1 px-2 py-1 border border-cyan-900/40 text-cyan-300/60 text-[9px] uppercase tracking-widest hover:border-cyan-500/60 hover:text-cyan-300 transition-all"
          data-testid="os-refresh-btn"
        >
          <RefreshCw size={11} /> {loading ? 'Syncing' : 'Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-3 p-4 border-b border-cyan-900/20">
        <StatCard
          icon={Cpu}
          label="CPU"
          value={status ? `${status.cpu_percent}%` : '—'}
          sublabel={status ? `${status.platform}` : 'system unavailable'}
        />
        <StatCard
          icon={Activity}
          label="Memory"
          value={status ? `${status.memory_percent}%` : '—'}
          sublabel={status ? `${status.memory_available_gb} GB free / ${status.memory_total_gb} GB total` : 'waiting for telemetry'}
        />
        <StatCard
          icon={HardDrive}
          label="Disk"
          value={status ? `${status.disk_percent}%` : '—'}
          sublabel={status ? `${status.disk_free_gb} GB free / ${status.disk_total_gb} GB total` : 'waiting for telemetry'}
        />
        <StatCard
          icon={Network}
          label="Services"
          value={status?.service_state ? `${status.service_state.tracked_services}` : `${services.length}`}
          sublabel={status?.service_state ? `${status.service_state.running_processes} active processes` : 'tracked runtime services'}
        />
      </div>

      <div className="grid grid-cols-4 gap-3 px-4 py-3 border-b border-cyan-900/20">
        <StatCard
          icon={MonitorSmartphone}
          label="Display"
          value={devices?.display?.available ? `${devices.display.width}×${devices.display.height}` : '—'}
          sublabel={devices?.machine || 'display telemetry'}
        />
        <StatCard
          icon={Camera}
          label="Camera"
          value={devices?.camera?.available ? 'Ready' : 'Unavailable'}
          sublabel={devices?.camera?.configured ? 'vision stack online' : 'hardware not detected'}
        />
        <StatCard
          icon={Mic}
          label="Mic"
          value={devices?.microphone?.available ? 'Ready' : 'Unavailable'}
          sublabel={devices?.tts?.available ? 'voice stack online' : 'speech engine not detected'}
        />
        <StatCard
          icon={BatteryCharging}
          label="Battery"
          value={devices?.battery?.available && devices.battery.percent !== null ? `${devices.battery.percent}%` : 'N/A'}
          sublabel={devices?.network ? `${devices.network.interfaces} network interfaces` : 'power telemetry'}
        />
      </div>

      <div className="grid grid-cols-12 flex-1 overflow-hidden">
        <div className="col-span-7 border-r border-cyan-900/20 overflow-hidden flex flex-col">
          <div className="px-4 py-2 border-b border-cyan-900/20 flex items-center gap-2">
            <Search size={12} className="text-cyan-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter processes by name, pid, user, command..."
              className="w-full bg-black/40 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none"
              data-testid="process-search"
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="sticky top-0 z-10 grid grid-cols-[96px_1fr_120px_96px_96px] gap-2 px-4 py-2 bg-slate-950/90 border-b border-cyan-900/20 text-[9px] font-display uppercase tracking-widest text-cyan-300/40">
              <span>PID</span>
              <span>Process</span>
              <span>User</span>
              <span>CPU%</span>
              <span>MEM%</span>
            </div>
            <div className="divide-y divide-cyan-900/10">
              {filteredProcesses.map((proc) => (
                <div key={proc.pid} className="grid grid-cols-[96px_1fr_120px_96px_96px] gap-2 px-4 py-3 text-[10px] font-mono text-cyan-100/90 hover:bg-cyan-950/20 transition-colors">
                  <span className="text-cyan-300/60">{proc.pid}</span>
                  <span className="truncate">{proc.name}</span>
                  <span className="truncate text-cyan-300/50">{proc.username || '—'}</span>
                  <span>{proc.cpu_percent}</span>
                  <span>{proc.memory_percent}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-5 flex flex-col overflow-hidden">
          <div className="px-4 py-2 border-b border-cyan-900/20 font-display text-[9px] tracking-widest uppercase text-cyan-300/50">
            JARVIS System Command
          </div>
          <div className="p-4 border-b border-cyan-900/20 space-y-3">
            <textarea
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="list processes, list services, launch calculator, etc."
              className="w-full h-24 resize-none bg-black/50 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none"
              data-testid="os-command-input"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={sendCommand}
                disabled={busy || !command.trim()}
                className="flex items-center gap-2 px-4 py-2 border border-cyan-500/40 text-cyan-400 font-display text-[10px] tracking-widest uppercase hover:bg-cyan-950/40 hover:border-cyan-400 disabled:opacity-30 transition-all"
                data-testid="os-command-send"
              >
                <Play size={12} /> {busy ? 'Routing' : 'Execute'}
              </button>
              <span className="font-mono text-[9px] text-cyan-300/35">Voice commands route through the same backend layer.</span>
            </div>
            {commandResult && (
              <div className="border border-cyan-900/30 bg-black/30 p-3 text-[10px] font-mono text-cyan-100/90">
                <div className="mb-1 text-cyan-400 uppercase tracking-widest">{commandResult.intent || 'result'}</div>
                <div>{commandResult.response || commandResult.error || 'No response.'}</div>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-cyan-900/20 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Audio Control</div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[9px]">
                <label className="flex items-center gap-2 text-cyan-300/70">
                  <Volume2 size={12} className="text-cyan-400" />
                  Volume
                </label>
                <span className="font-mono text-cyan-100">{Math.round(volumeControl !== null ? volumeControl : (audio?.volume || 0))}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={volumeControl !== null ? volumeControl : (audio?.volume || 0)}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="w-full h-2 bg-cyan-950/40 border border-cyan-900/30 cursor-pointer accent-cyan-500 hover:accent-cyan-400"
                data-testid="volume-slider"
              />
            </div>

            <div className="flex items-center justify-between p-2 border border-cyan-900/30 bg-slate-950/30 rounded">
              <div className="flex items-center gap-2">
                <Mic size={12} className={audio?.microphone_enabled ? 'text-cyan-400' : 'text-cyan-900'} />
                <span className="font-mono text-[9px] text-cyan-300/70">Microphone</span>
              </div>
              <button
                onClick={handleMicrophoneToggle}
                className={`px-3 py-1 border text-[9px] font-display tracking-widest uppercase transition-all ${
                  audio?.microphone_enabled
                    ? 'border-green-500/40 bg-green-950/20 text-green-400 hover:bg-green-950/40'
                    : 'border-red-500/40 bg-red-950/20 text-red-400 hover:bg-red-950/40'
                }`}
                data-testid="microphone-toggle"
              >
                {audio?.microphone_enabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>

            {audio && (
              <div className="text-[9px] text-cyan-300/40 font-mono space-y-1">
                <div>• {audio.default_input ? `IN: ${audio.default_input.substring(0, 40)}` : 'No input device'}</div>
                <div>• {audio.default_output ? `OUT: ${audio.default_output.substring(0, 40)}` : 'No output device'}</div>
                <div>• {audio.device_count} audio device{audio.device_count !== 1 ? 's' : ''} detected</div>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-cyan-900/20 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Vision System</div>
            
            <div className="flex items-center gap-2 p-2 border border-cyan-900/30 bg-slate-950/30 rounded">
              <Camera size={12} className={camera?.available ? 'text-cyan-400' : 'text-cyan-900'} />
              <span className="font-mono text-[9px] text-cyan-300/70">Camera</span>
              <button
                onClick={camera?.enabled ? handleCameraDisable : handleCameraEnable}
                disabled={!camera?.available}
                className={`ml-auto px-3 py-1 border text-[9px] font-display tracking-widest uppercase transition-all disabled:opacity-40 ${
                  camera?.enabled
                    ? 'border-green-500/40 bg-green-950/20 text-green-400 hover:bg-green-950/40'
                    : 'border-amber-500/40 bg-amber-950/20 text-amber-400 hover:bg-amber-950/40'
                }`}
                data-testid="camera-toggle"
              >
                {camera?.enabled ? 'Active' : 'Inactive'}
              </button>
            </div>

            {camera?.enabled && (
              <>
                <div className="space-y-2">
                  <button
                    onClick={handleCaptureSnapshot}
                    disabled={snapshotBusy}
                    className="w-full p-2 border border-cyan-500/40 bg-cyan-950/20 text-cyan-400 text-[10px] font-display tracking-widest uppercase hover:bg-cyan-950/40 disabled:opacity-40 transition-all"
                    data-testid="capture-snapshot"
                  >
                    {snapshotBusy ? 'Capturing...' : 'Capture Snapshot'}
                  </button>
                  
                  <div className="flex items-center justify-between p-2 border border-cyan-900/30 bg-slate-950/30 rounded">
                    <span className="font-mono text-[9px] text-cyan-300/70">Face Detection</span>
                    <button
                      onClick={handleFaceDetectionToggle}
                      className={`px-2 py-1 border text-[9px] font-display tracking-widest uppercase transition-all ${
                        camera?.face_detection_active
                          ? 'border-green-500/40 bg-green-950/20 text-green-400 hover:bg-green-950/40'
                          : 'border-gray-500/40 bg-gray-950/20 text-gray-400 hover:bg-gray-950/40'
                      }`}
                      data-testid="face-detection-toggle"
                    >
                      {camera?.face_detection_active ? 'Active' : 'Off'}
                    </button>
                  </div>
                </div>

                {snapshot && (
                  <div className="border border-cyan-900/30 bg-slate-950/50 p-2 space-y-1">
                    <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest">Snapshot</div>
                    <div className="w-full bg-black border border-cyan-900/20 flex items-center justify-center overflow-hidden" style={{ aspectRatio: snapshot.width / snapshot.height || '16/9' }}>
                      {snapshot.jpeg_base64 && (
                        <img src={`data:image/jpeg;base64,${snapshot.jpeg_base64}`} alt="Snapshot" className="w-full h-full object-contain" />
                      )}
                    </div>
                    <div className="text-[9px] font-mono text-cyan-300/40">
                      <div>Resolution: {snapshot.width}×{snapshot.height}</div>
                      {snapshot.face_count > 0 && <div className="text-green-400">Faces detected: {snapshot.face_count}</div>}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="p-4 border-t border-cyan-900/20 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Voice Control</div>
            
            {voice && (
              <>
                <button
                  onClick={handleVoiceListen}
                  disabled={voiceListenBusy}
                  className="w-full p-2 border border-cyan-500/40 bg-cyan-950/20 text-cyan-400 text-[10px] font-display tracking-widest uppercase hover:bg-cyan-950/40 disabled:opacity-40 transition-all"
                  data-testid="voice-listen"
                >
                  <span className={voiceListening ? 'animate-pulse' : ''}>
                    {voiceListenBusy ? 'Listening...' : 'Listen for Command'}
                  </span>
                </button>

                <div className="border border-cyan-900/30 bg-slate-950/30 p-2 space-y-1">
                  <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest">Mode</div>
                  <div className="font-mono text-sm text-cyan-400">{voice.state?.mode || 'IDLE'}</div>
                  <div className="text-[9px] font-mono text-cyan-300/40">
                    <div>Wake Word: {voice.state?.wake_word_enabled ? 'Enabled' : 'Disabled'}</div>
                    <div>Confidence: {(voice.state?.average_confidence * 100).toFixed(0)}%</div>
                    <div>Mics: {voice.state?.microphones || 0} / Speakers: {voice.state?.speakers || 0}</div>
                  </div>
                </div>

                {voiceTranscription && (
                  <div className="border border-green-900/30 bg-green-950/20 p-2 space-y-1">
                    <div className="text-[9px] text-green-300/70 uppercase tracking-widest">Last Command</div>
                    <div className="font-mono text-sm text-green-400">"{voiceTranscription.text}"</div>
                    <div className="text-[9px] font-mono text-green-300/40">
                      <div>Confidence: {(voiceTranscription.confidence * 100).toFixed(0)}%</div>
                      <div>Language: {voiceTranscription.language}</div>
                      <div>Duration: {voiceTranscription.duration_ms}ms</div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="p-4 border-t border-cyan-900/20 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Power Management</div>
            
            {power && (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="border border-cyan-900/30 bg-slate-950/30 p-2 rounded">
                    <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest mb-1">Power Source</div>
                    <div className="font-mono text-sm text-cyan-100">
                      {power.ac_powered ? '🔌 AC Power' : '🔋 Battery'}
                    </div>
                  </div>
                  {power.battery_percent !== null && (
                    <div className={`border p-2 rounded ${
                      power.critical_battery ? 'border-red-500/40 bg-red-950/20' :
                      power.low_battery ? 'border-amber-500/40 bg-amber-950/20' :
                      'border-cyan-900/30 bg-slate-950/30'
                    }`}>
                      <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest mb-1">Battery</div>
                      <div className={`font-mono text-sm ${
                        power.critical_battery ? 'text-red-300' :
                        power.low_battery ? 'text-amber-300' :
                        'text-cyan-100'
                      }`}>
                        {Math.round(power.battery_percent)}%
                      </div>
                    </div>
                  )}
                </div>

                {power.estimated_runtime_minutes !== null && (
                  <div className="text-[9px] font-mono text-cyan-300/50">
                    Estimated runtime: {Math.floor(power.estimated_runtime_minutes / 60)}h {Math.round(power.estimated_runtime_minutes % 60)}m
                  </div>
                )}

                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => setPowerConfirmation('sleep')}
                    disabled={powerActionBusy}
                    className="p-2 border border-cyan-500/40 bg-cyan-950/20 text-cyan-400 text-[9px] font-display tracking-widest uppercase hover:bg-cyan-950/40 disabled:opacity-40 transition-all"
                    data-testid="power-sleep-btn"
                  >
                    Sleep
                  </button>
                  <button
                    onClick={() => setPowerConfirmation('restart')}
                    disabled={powerActionBusy}
                    className="p-2 border border-amber-500/40 bg-amber-950/20 text-amber-400 text-[9px] font-display tracking-widest uppercase hover:bg-amber-950/40 disabled:opacity-40 transition-all"
                    data-testid="power-restart-btn"
                  >
                    Restart
                  </button>
                  <button
                    onClick={() => setPowerConfirmation('shutdown')}
                    disabled={powerActionBusy}
                    className="p-2 border border-red-500/40 bg-red-950/20 text-red-400 text-[9px] font-display tracking-widest uppercase hover:bg-red-950/40 disabled:opacity-40 transition-all"
                    data-testid="power-shutdown-btn"
                  >
                    Shutdown
                  </button>
                </div>

                {powerConfirmation && (
                  <div className="border border-amber-500/40 bg-amber-950/30 p-3 space-y-2">
                    <div className="text-[10px] text-amber-300 uppercase tracking-widest font-display">
                      ⚠️ Confirm {powerConfirmation}
                    </div>
                    <div className="text-[9px] text-amber-200">
                      {powerConfirmation === 'sleep' && 'System will enter sleep mode. Press again to confirm.'}
                      {powerConfirmation === 'restart' && 'System will restart in 30 seconds. Unsaved work will be lost.'}
                      {powerConfirmation === 'shutdown' && 'System will shut down in 30 seconds. Unsaved work will be lost.'}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handlePowerAction(powerConfirmation)}
                        disabled={powerActionBusy}
                        className="flex-1 p-2 border border-amber-500/60 bg-amber-500/20 text-amber-300 text-[9px] font-display tracking-widest uppercase hover:bg-amber-500/30 disabled:opacity-40 transition-all"
                        data-testid="power-confirm-btn"
                      >
                        {powerActionBusy ? 'Processing...' : 'CONFIRM'}
                      </button>
                      <button
                        onClick={() => setPowerConfirmation(null)}
                        disabled={powerActionBusy}
                        className="flex-1 p-2 border border-cyan-900/40 bg-slate-950/40 text-cyan-300/70 text-[9px] font-display tracking-widest uppercase hover:bg-slate-950/60 disabled:opacity-40 transition-all"
                        data-testid="power-cancel-confirm-btn"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="p-4 border-t border-cyan-900/20 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Network Status</div>
            
            {network && network.data && (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="border border-cyan-900/30 bg-slate-950/30 p-2 rounded">
                    <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest mb-1">Connected Interfaces</div>
                    <div className="font-mono text-sm text-cyan-100">
                      {network.data.connected_interfaces?.length || 0} active
                    </div>
                  </div>
                  <div className={`border p-2 rounded flex items-center gap-2 ${
                    network.data.wifi_enabled ? 'border-green-500/40 bg-green-950/20' : 'border-cyan-900/30 bg-slate-950/30'
                  }`}>
                    {network.data.wifi_enabled ? (
                      <Wifi size={14} className="text-green-400" />
                    ) : (
                      <WifiOff size={14} className="text-cyan-400" />
                    )}
                    <div className="flex-1">
                      <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest">WiFi</div>
                      <div className={`font-mono text-xs ${network.data.wifi_enabled ? 'text-green-300' : 'text-cyan-300/50'}`}>
                        {network.data.wifi_enabled ? 'Enabled' : 'Disabled'}
                      </div>
                    </div>
                  </div>
                </div>

                {network.data.current_ssid && (
                  <div className="border border-cyan-900/30 bg-slate-950/30 p-2 rounded text-[9px]">
                    <span className="text-cyan-300/50 uppercase tracking-widest">Connected: </span>
                    <span className="font-mono text-cyan-100">{network.data.current_ssid}</span>
                  </div>
                )}

                {network.data.connected_interfaces && network.data.connected_interfaces.length > 0 && (
                  <div className="border border-cyan-900/30 bg-slate-950/20 p-2 rounded space-y-1">
                    <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest mb-2">IP Addresses</div>
                    {network.data.connected_interfaces.map((iface, idx) => (
                      <div key={idx} className="text-[9px] font-mono text-cyan-300/70">
                        <span className="text-cyan-400">{iface.name}</span>
                        {iface.ip_address && <span>: {iface.ip_address}</span>}
                      </div>
                    ))}
                  </div>
                )}

                {network.data.dns_servers && network.data.dns_servers.length > 0 && (
                  <div className="text-[9px] font-mono text-cyan-300/50 space-y-1">
                    <div className="text-cyan-300/60">DNS Servers:</div>
                    {network.data.dns_servers.map((dns, idx) => (
                      <div key={idx} className="text-cyan-300/40">• {dns}</div>
                    ))}
                  </div>
                )}

                {network.data.wifi_networks && network.data.wifi_networks.length > 0 && (
                  <div className="border border-cyan-900/30 bg-slate-950/20 p-2 rounded space-y-1">
                    <div className="text-[9px] text-cyan-300/50 uppercase tracking-widest mb-2">Available WiFi ({network.data.wifi_networks.length})</div>
                    {network.data.wifi_networks.slice(0, 5).map((net, idx) => (
                      <div key={idx} className="flex items-center justify-between text-[9px]">
                        <div className="flex-1 truncate text-cyan-300/70">{net.ssid}</div>
                        <div className="flex items-center gap-1 text-cyan-400">
                          <span className="font-mono">{net.signal_strength}%</span>
                          <span className="text-[8px]">{net.security}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {network.data.vpn_connected && (
                  <div className="border border-purple-500/40 bg-purple-950/20 p-2 rounded flex items-center gap-2">
                    <Globe size={12} className="text-purple-400" />
                    <span className="text-[9px] font-mono text-purple-300">VPN Connected</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            <div className="font-display text-[9px] tracking-widest uppercase text-cyan-300/50">Tracked Services</div>
            {killable.length === 0 ? (
              <div className="text-cyan-300/30 font-mono text-xs">No tracked services are currently running.</div>
            ) : (
              killable.map((service) => (
                <div key={service.name} className="border border-cyan-900/20 p-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs text-cyan-100">{service.name}</div>
                    <div className="font-mono text-[9px] text-cyan-300/35">PID {service.pid} • {service.directory || 'workspace root'}</div>
                  </div>
                  <div className="font-mono text-[9px] uppercase tracking-widest text-green-400">Running</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
