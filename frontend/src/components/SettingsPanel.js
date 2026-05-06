import React, { useState, useRef, useEffect } from 'react';
import { Camera, ShieldCheck, UserCheck, AlertCircle, RefreshCw } from 'lucide-react';

export default function SettingsPanel({ api, token }) {
  const [cameraActive, setCameraActive] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollStatus, setEnrollStatus] = useState(null);
  const [enrolledFaces, setEnrolledFaces] = useState(0);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 400, height: 400, facingMode: 'user' }
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraActive(true);
    } catch (e) {
      setEnrollStatus({ success: false, message: 'Camera access denied: ' + e.message });
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  const captureAndEnroll = async () => {
    if (!videoRef.current || !cameraActive) return;
    setEnrolling(true);
    setEnrollStatus(null);

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 400;
    canvas.height = videoRef.current.videoHeight || 400;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg', 0.9);

    try {
      const resp = await fetch(`${api}/api/auth/enroll_face`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ image: imageData, label: 'owner' }),
      });
      const data = await resp.json();
      setEnrollStatus(data);
      if (data.success) {
        setEnrolledFaces(prev => prev + 1);
      }
    } catch (e) {
      setEnrollStatus({ success: false, message: 'Network error: ' + e.message });
    } finally {
      setEnrolling(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-4 overflow-y-auto" data-testid="settings-panel">
      {/* Face Enrollment Section */}
      <div className="border border-cyan-900/50 p-4 mb-4">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-4 flex items-center gap-2">
          <UserCheck size={14} /> Biometric Face Enrollment
        </h3>

        <p className="font-mono text-[10px] text-cyan-300/50 mb-4 leading-relaxed">
          Enroll your face for secure biometric login. Once enrolled, JARVIS will recognize you
          and deny access to unrecognized individuals.
        </p>

        {/* Camera Feed */}
        <div className="relative w-48 h-48 mx-auto mb-4 border border-cyan-500/30 overflow-hidden bg-black">
          {cameraActive ? (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
                style={{ filter: 'grayscale(0.5) contrast(1.1)', opacity: 0.85 }}
              />
              {/* Corner brackets */}
              <div className="absolute top-2 left-2 w-4 h-4 border-t border-l border-cyan-400" />
              <div className="absolute top-2 right-2 w-4 h-4 border-t border-r border-cyan-400" />
              <div className="absolute bottom-2 left-2 w-4 h-4 border-b border-l border-cyan-400" />
              <div className="absolute bottom-2 right-2 w-4 h-4 border-b border-r border-cyan-400" />
              {/* Crosshairs */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-3 h-px bg-cyan-400/60" />
                <div className="absolute w-px h-3 bg-cyan-400/60" />
              </div>
              <div className="absolute bottom-1 left-1 right-1 text-center">
                <span className="font-mono text-[8px] text-green-400 bg-black/60 px-1">LIVE FEED</span>
              </div>
            </>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center">
              <Camera size={24} className="text-cyan-900 mb-2" />
              <span className="font-mono text-[9px] text-cyan-900">CAMERA INACTIVE</span>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex justify-center gap-3 mb-4">
          {!cameraActive ? (
            <button
              onClick={startCamera}
              className="flex items-center gap-2 px-4 py-2 border border-cyan-500/40 text-cyan-400 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/40 transition-all"
              data-testid="start-camera-btn"
            >
              <Camera size={12} /> Activate Camera
            </button>
          ) : (
            <>
              <button
                onClick={captureAndEnroll}
                disabled={enrolling}
                className="flex items-center gap-2 px-4 py-2 border border-green-500/40 text-green-400 font-display text-[9px] tracking-wider uppercase hover:bg-green-950/30 disabled:opacity-40 transition-all"
                data-testid="enroll-face-btn"
              >
                {enrolling ? <RefreshCw size={12} className="animate-spin" /> : <ShieldCheck size={12} />}
                {enrolling ? 'Enrolling...' : 'Capture & Enroll'}
              </button>
              <button
                onClick={stopCamera}
                className="flex items-center gap-2 px-3 py-2 border border-red-900/40 text-red-400/70 font-display text-[9px] tracking-wider uppercase hover:text-red-400 transition-all"
                data-testid="stop-camera-btn"
              >
                Stop
              </button>
            </>
          )}
        </div>

        {/* Status */}
        {enrollStatus && (
          <div className={`flex items-start gap-2 p-3 border ${
            enrollStatus.success ? 'border-green-500/30 bg-green-950/20' : 'border-red-500/30 bg-red-950/20'
          }`} data-testid="enroll-status">
            {enrollStatus.success ? (
              <ShieldCheck size={14} className="text-green-400 mt-0.5 flex-shrink-0" />
            ) : (
              <AlertCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
            )}
            <span className={`font-mono text-[10px] ${enrollStatus.success ? 'text-green-400' : 'text-red-400'}`}>
              {enrollStatus.message}
            </span>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-4 space-y-1">
          <div className="font-display text-[8px] tracking-widest text-cyan-300/40 uppercase mb-2">Enrollment Protocol:</div>
          <div className="font-mono text-[9px] text-cyan-300/30">1. Activate camera and position face clearly</div>
          <div className="font-mono text-[9px] text-cyan-300/30">2. Ensure good lighting — face centered in frame</div>
          <div className="font-mono text-[9px] text-cyan-300/30">3. Click "Capture & Enroll" to store biometric profile</div>
          <div className="font-mono text-[9px] text-cyan-300/30">4. Login will verify face against enrolled profile</div>
        </div>
      </div>

      {/* System Info */}
      <div className="border border-cyan-900/50 p-4">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">System Configuration</h3>
        <div className="space-y-2">
          <div className="flex justify-between py-1 border-b border-cyan-900/20">
            <span className="font-mono text-[9px] text-cyan-300/40">LLM Provider</span>
            <span className="font-mono text-[9px] text-cyan-100">Gemini 2.5 Flash</span>
          </div>
          <div className="flex justify-between py-1 border-b border-cyan-900/20">
            <span className="font-mono text-[9px] text-cyan-300/40">Fallback</span>
            <span className="font-mono text-[9px] text-cyan-100">Ollama (llama3.1)</span>
          </div>
          <div className="flex justify-between py-1 border-b border-cyan-900/20">
            <span className="font-mono text-[9px] text-cyan-300/40">Face Enrolled</span>
            <span className="font-mono text-[9px] text-green-400">{enrolledFaces > 0 ? 'YES' : 'NOT YET'}</span>
          </div>
          <div className="flex justify-between py-1 border-b border-cyan-900/20">
            <span className="font-mono text-[9px] text-cyan-300/40">VSCode Extension</span>
            <span className="font-mono text-[9px] text-cyan-100">Ready (port 8001)</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="font-mono text-[9px] text-cyan-300/40">Organization</span>
            <span className="font-mono text-[9px] text-cyan-400">Sypher Industries</span>
          </div>
        </div>
      </div>
    </div>
  );
}
