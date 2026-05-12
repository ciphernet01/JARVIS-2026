import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Scan, ShieldCheck, Camera, AlertTriangle } from 'lucide-react';

export default function LoginScreen({ onLogin, api }) {
  const [status, setStatus] = useState('AWAITING BIOMETRIC INPUT');
  const [scanning, setScanning] = useState(false);
  const [granted, setGranted] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [faceBox, setFaceBox] = useState(null);
  const [faceInfo, setFaceInfo] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  useEffect(() => {
    initCamera();
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const initCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      });
      streamRef.current = stream;
      setCameraActive(true);
      setStatus('NEURAL LINK ESTABLISHED. CAMERA ONLINE.');
    } catch (err) {
      setCameraError(err.message);
      setStatus('CAMERA OFFLINE. PRODUCTION BYPASS READY.');
    }
  };

  // Attach stream to video element AFTER it renders
  useEffect(() => {
    if (cameraActive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [cameraActive]);

  const captureFrame = () => {
    if (!videoRef.current || !cameraActive) return null;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0);
    return canvas.toDataURL('image/jpeg', 0.85);
  };

  const startScan = async () => {
    setScanning(true);
    setStatus(cameraActive ? 'SCANNING BIOMETRICS...' : 'CAMERA OFFLINE. AUTHORIZING PRODUCTION BYPASS...');
    setFaceInfo(null);
    setFaceBox(null);

    const imageData = captureFrame();
    await new Promise(r => setTimeout(r, cameraActive ? 1500 : 600));

    try {
      const resp = await fetch(`${api}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: imageData ? 'biometric' : 'camera_unavailable',
          image: imageData,
        }),
      });
      const data = await resp.json();

      if (data.face_box) {
        setFaceBox(data.face_box);
      }

      if (data.success) {
        setStatus('ACCESS GRANTED');
        setGranted(true);
        setFaceInfo({ detected: data.face_detected, confidence: data.confidence });
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
        }
        setTimeout(() => onLogin(data.token), 1800);
      } else {
        setStatus(data.message || 'ACCESS DENIED');
        setFaceInfo({
          detected: data.face_detected,
          confidence: data.confidence,
        });
        setScanning(false);
      }
    } catch (e) {
      setStatus('NEURAL LINK ERROR: ' + e.message);
      setScanning(false);
    }
  };

  const handleBypass = async () => {
    setScanning(true);
    setStatus('AUTHORIZING PRODUCTION BYPASS...');
    try {
      const resp = await fetch(`${api}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method: 'production_bypass',
          image: null,
        }),
      });
      const data = await resp.json();
      if (data.success) {
        setStatus('ACCESS GRANTED (BYPASS)');
        setGranted(true);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
        }
        setTimeout(() => onLogin(data.token), 1000);
      } else {
        setStatus(data.message || 'BYPASS DENIED');
        setScanning(false);
      }
    } catch (e) {
      setStatus('NEURAL LINK ERROR: ' + e.message);
      setScanning(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" data-testid="login-screen">
      {/* Background */}
      <div className="absolute inset-0 bg-slate-950">
        <div className="absolute inset-0 opacity-20" style={{
          background: 'radial-gradient(circle at top, rgba(6,182,212,0.18), transparent 35%), radial-gradient(circle at bottom, rgba(14,165,233,0.14), transparent 30%), linear-gradient(180deg, rgba(2,6,23,0.96), rgba(2,6,23,0.92))',
        }} />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(6,182,212,0.04)_1px,transparent_1px),linear-gradient(rgba(6,182,212,0.04)_1px,transparent_1px)] bg-[size:48px_48px] opacity-30" />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/40 via-transparent to-slate-950" />
      </div>

      <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-20 font-mono text-[9px] tracking-[0.2em] uppercase text-cyan-300/40">
        <span>Sypher Industries // J.A.R.V.I.S OS</span>
        <span>Voice-first shell active</span>
      </div>

      {/* Login Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`relative z-10 text-center p-10 border bg-slate-950/80 backdrop-blur-xl transition-all duration-1000 ${
          granted ? 'border-green-400/60 shadow-[0_0_60px_rgba(34,197,94,0.3)]' : 'border-cyan-500/30'
        }`}
        data-testid="login-container"
      >
        <div className="mb-4 inline-flex items-center gap-2 px-3 py-1 border border-cyan-500/20 bg-cyan-950/20 text-cyan-300/70 font-mono text-[9px] tracking-[0.25em] uppercase">
          <Scan size={10} /> System entry // biometric + voice
        </div>

        {/* Title */}
        <h1 className="font-display text-4xl tracking-tighter uppercase text-cyan-400 mb-1" style={{ textShadow: '0 0 20px rgba(6,182,212,0.5)' }}>
          J.A.R.V.I.S OS
        </h1>
        <p className="font-display text-xs tracking-[0.2em] uppercase text-cyan-300/60 mb-6">
          Sypher Industries // Debian Shell Interface
        </p>

        {/* Camera Feed - Large and visible */}
        <div className="relative w-72 h-56 mx-auto mb-5 border border-cyan-500/40 overflow-hidden bg-black">
          {/* Corner brackets */}
          <div className="absolute top-2 left-2 w-5 h-5 border-t-2 border-l-2 border-cyan-400 z-20" />
          <div className="absolute top-2 right-2 w-5 h-5 border-t-2 border-r-2 border-cyan-400 z-20" />
          <div className="absolute bottom-2 left-2 w-5 h-5 border-b-2 border-l-2 border-cyan-400 z-20" />
          <div className="absolute bottom-2 right-2 w-5 h-5 border-b-2 border-r-2 border-cyan-400 z-20" />

          {/* Live webcam feed */}
          {cameraActive ? (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover z-[5]"
              style={{ transform: 'scaleX(-1)' }}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              {cameraError ? (
                <>
                  <AlertTriangle className="w-10 h-10 text-amber-400/60 mb-2" />
                  <span className="text-[9px] text-amber-400/60 font-mono">CAMERA OFFLINE</span>
                  <span className="text-[8px] text-amber-400/40 font-mono mt-1">Production bypass available</span>
                </>
              ) : (
                <>
                  <Camera className="w-10 h-10 text-cyan-400/40 mb-2" />
                  <span className="text-[9px] text-cyan-400/40 font-mono">INITIALIZING...</span>
                </>
              )}
            </div>
          )}

          {/* Face detection bounding box */}
          {faceBox && (
            <div
              className="absolute border-2 border-cyan-400 z-20 transition-all duration-300"
              style={{
                left: `${(1 - faceBox.x - faceBox.w) * 100}%`,
                top: `${faceBox.y * 100}%`,
                width: `${faceBox.w * 100}%`,
                height: `${faceBox.h * 100}%`,
                boxShadow: '0 0 10px rgba(6,182,212,0.5)',
              }}
            >
              <div className="absolute -top-4 left-0 font-mono text-[8px] text-cyan-400 bg-black/70 px-1">
                FACE DETECTED
              </div>
            </div>
          )}

          {/* Center guide - shows where to place face */}
          {cameraActive && !faceBox && !granted && (
            <div className="absolute inset-0 flex items-center justify-center z-[15] pointer-events-none">
              <div className="w-32 h-40 border-2 border-dashed border-cyan-400/40 rounded-full flex items-center justify-center">
                <span className="font-mono text-[8px] text-cyan-400/60 text-center px-2">
                  POSITION<br/>FACE HERE
                </span>
              </div>
            </div>
          )}

          {/* Scan line */}
          {scanning && (
            <motion.div
              className="absolute left-0 right-0 h-0.5 bg-cyan-400 z-30"
              style={{ boxShadow: '0 0 12px #06b6d4, 0 0 24px #06b6d4' }}
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            />
          )}

          {/* Granted overlay */}
          {granted && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="absolute inset-0 bg-green-500/20 flex items-center justify-center z-30"
            >
              <ShieldCheck className="w-16 h-16 text-green-400" />
            </motion.div>
          )}

          {/* Top-right status badge */}
          <div className="absolute top-2 right-8 z-20">
            {cameraActive && (
              <span className="font-mono text-[7px] text-green-400 bg-black/70 px-1 py-0.5 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                LIVE
              </span>
            )}
          </div>
        </div>

        {/* Confidence bar */}
        {faceInfo && faceInfo.detected && (
          <div className="w-72 mx-auto mb-3">
            <div className="flex justify-between font-mono text-[8px] text-cyan-300/50 mb-1">
              <span>MATCH CONFIDENCE</span>
              <span>{(faceInfo.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1 bg-cyan-900/30 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${faceInfo.confidence * 100}%` }}
                className={`h-full ${faceInfo.confidence > 0.5 ? 'bg-green-400' : faceInfo.confidence > 0.3 ? 'bg-amber-400' : 'bg-red-400'}`}
              />
            </div>
          </div>
        )}

        {/* Status */}
        <p className={`font-mono text-[10px] tracking-[0.12em] mb-5 ${
          granted ? 'text-green-400' : scanning ? 'text-cyan-400' : faceInfo && !faceInfo.detected ? 'text-red-400' : 'text-cyan-300/60'
        }`} data-testid="login-status">
          {status}
        </p>

        {/* Auth Buttons */}
        {!scanning && !granted && (
          <div className="flex flex-col gap-3 justify-center items-center">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={startScan}
              className="px-8 py-3 border border-cyan-500/60 text-cyan-400 font-display text-xs tracking-[0.2em] uppercase hover:bg-cyan-950/40 hover:border-cyan-400 transition-all duration-200 w-full max-w-[280px]"
              data-testid="login-scan-button"
            >
              <span className="inline-flex items-center gap-2 justify-center">{cameraActive ? <Scan size={12} /> : <Scan size={12} />} {cameraActive ? 'Initialize Bio-Scan' : 'Enter JARVIS'}</span>
            </motion.button>
            
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleBypass}
              className="px-8 py-2 border border-slate-600/60 text-slate-400 font-display text-[10px] tracking-[0.2em] uppercase hover:bg-slate-800/40 hover:text-cyan-400 hover:border-cyan-900/60 transition-all duration-200 w-full max-w-[280px]"
              data-testid="login-bypass-button"
            >
              Enable Override Bypass
            </motion.button>
          </div>
        )}

        {/* Hint after failure */}
        {!scanning && !granted && faceInfo && !faceInfo.detected && (
          <p className="mt-3 text-[9px] text-amber-400/60 font-mono">
            Position your face within the oval guide and ensure good lighting
          </p>
        )}

        {/* Reference info */}
        <p className="mt-4 font-mono text-[8px] text-cyan-900/60">
          {cameraActive
            ? 'Matching against: imagedata/ folder + enrolled profiles'
            : 'Camera unavailable: secured local production bypass'}
        </p>

        <div className="mt-4 flex items-center justify-center gap-3 font-mono text-[8px] tracking-[0.18em] uppercase text-cyan-300/35">
          <span>Voice</span>
          <span>•</span>
          <span>Vision</span>
          <span>•</span>
          <span>Filesystem</span>
          <span>•</span>
          <span>System Control</span>
        </div>
      </motion.div>
    </div>
  );
}
