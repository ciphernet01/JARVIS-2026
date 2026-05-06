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
  const canvasRef = useRef(null);

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
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraActive(true);
      setStatus('NEURAL LINK ESTABLISHED. CAMERA ONLINE.');
    } catch (err) {
      setCameraError(err.message);
      setStatus('CAMERA OFFLINE. FALLBACK MODE AVAILABLE.');
    }
  };

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
    setStatus('SCANNING BIOMETRICS...');
    setFaceInfo(null);
    setFaceBox(null);

    const imageData = captureFrame();
    await new Promise(r => setTimeout(r, 1500));

    try {
      const resp = await fetch(`${api}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: 'biometric', image: imageData }),
      });
      const data = await resp.json();

      if (data.face_box) {
        setFaceBox(data.face_box);
      }

      if (data.success) {
        setStatus('ACCESS GRANTED');
        setGranted(true);
        setFaceInfo({ detected: true, confidence: data.confidence });
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

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" data-testid="login-screen">
      {/* Background */}
      <div className="absolute inset-0 bg-slate-950">
        <div className="absolute inset-0 opacity-15" style={{
          backgroundImage: `url(https://images.unsplash.com/photo-1698571262509-5e96d6c64bd1?w=1200)`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'hue-rotate(180deg) saturate(0.5)',
        }} />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-transparent to-slate-950" />
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
        {/* Title */}
        <h1 className="font-display text-4xl tracking-tighter uppercase text-cyan-400 mb-1" style={{ textShadow: '0 0 20px rgba(6,182,212,0.5)' }}>
          J.A.R.V.I.S
        </h1>
        <p className="font-display text-xs tracking-[0.2em] uppercase text-cyan-300/60 mb-6">
          Sypher Industries // Security Protocol
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
                  <span className="text-[8px] text-amber-400/40 font-mono mt-1">Grant camera permission</span>
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

        {/* Auth Button */}
        {!scanning && !granted && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={startScan}
            className="px-8 py-3 border border-cyan-500/60 text-cyan-400 font-display text-xs tracking-[0.2em] uppercase hover:bg-cyan-950/40 hover:border-cyan-400 transition-all duration-200"
            data-testid="login-scan-button"
          >
            {cameraActive ? 'Initialize Bio-Scan' : 'Bypass Authentication'}
          </motion.button>
        )}

        {/* Hint after failure */}
        {!scanning && !granted && faceInfo && !faceInfo.detected && (
          <p className="mt-3 text-[9px] text-amber-400/60 font-mono">
            Position your face within the oval guide and ensure good lighting
          </p>
        )}

        {/* Reference info */}
        <p className="mt-4 font-mono text-[8px] text-cyan-900/60">
          Matching against: imagedata/ folder + enrolled profiles
        </p>
      </motion.div>
    </div>
  );
}
