import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Scan, ShieldCheck, Camera, AlertTriangle } from 'lucide-react';

export default function LoginScreen({ onLogin, api }) {
  const [status, setStatus] = useState('AWAITING BIOMETRIC INPUT');
  const [scanning, setScanning] = useState(false);
  const [granted, setGranted] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [faceInfo, setFaceInfo] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Initialize camera on mount
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
        video: { width: 400, height: 400, facingMode: 'user' }
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
    canvas.width = videoRef.current.videoWidth || 400;
    canvas.height = videoRef.current.videoHeight || 400;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0);
    return canvas.toDataURL('image/jpeg', 0.8);
  };

  const startScan = async () => {
    setScanning(true);
    setStatus('SCANNING BIOMETRICS...');
    setFaceInfo(null);

    // Capture webcam frame
    const imageData = captureFrame();

    // Wait for scan animation
    await new Promise(r => setTimeout(r, 2000));

    try {
      const resp = await fetch(`${api}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: 'biometric', image: imageData }),
      });
      const data = await resp.json();

      if (data.success) {
        setStatus('ACCESS GRANTED');
        setGranted(true);
        setFaceInfo({
          detected: data.face_detected,
          confidence: data.confidence,
        });

        // Stop camera
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
        className={`relative z-10 text-center p-12 border bg-slate-950/80 backdrop-blur-xl transition-all duration-1000 ${
          granted ? 'border-green-400/60 shadow-[0_0_60px_rgba(34,197,94,0.3)]' : 'border-cyan-500/30'
        }`}
        data-testid="login-container"
      >
        {/* Title */}
        <h1 className="font-display text-4xl tracking-tighter uppercase text-cyan-400 mb-1" style={{ textShadow: '0 0 20px rgba(6,182,212,0.5)' }}>
          J.A.R.V.I.S
        </h1>
        <p className="font-display text-xs tracking-[0.2em] uppercase text-cyan-300/60 mb-8">
          Neural Interface Security Protocol
        </p>

        {/* Scanner Box with Live Camera */}
        <div className="relative w-56 h-56 mx-auto mb-6 border border-cyan-500/40 overflow-hidden">
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
              className="absolute inset-0 w-full h-full object-cover"
              style={{ filter: 'grayscale(0.7) contrast(1.2) brightness(0.9)', opacity: 0.8 }}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              {cameraError ? (
                <>
                  <AlertTriangle className="w-10 h-10 text-amber-400/60 mb-2" />
                  <span className="text-[9px] text-amber-400/60 font-mono">CAMERA OFFLINE</span>
                </>
              ) : (
                <>
                  <Camera className="w-10 h-10 text-cyan-400/40 mb-2" />
                  <span className="text-[9px] text-cyan-400/40 font-mono">INITIALIZING...</span>
                </>
              )}
            </div>
          )}

          {/* Cyan overlay on video */}
          <div className="absolute inset-0 bg-cyan-900/20 mix-blend-overlay z-10 pointer-events-none" />

          {/* Scan line animation */}
          {scanning && (
            <motion.div
              className="absolute left-0 right-0 h-0.5 bg-cyan-400 z-30"
              style={{ boxShadow: '0 0 12px #06b6d4, 0 0 24px #06b6d4' }}
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            />
          )}

          {/* Crosshairs */}
          <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
            <div className="w-12 h-12">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-0.5 bg-cyan-400/50" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-0.5 h-4 bg-cyan-400/50" />
            </div>
          </div>

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

          {/* Face detection indicator */}
          {faceInfo && faceInfo.detected && !granted && (
            <div className="absolute bottom-3 left-3 right-3 z-20">
              <div className="bg-black/70 px-2 py-1 text-[8px] font-mono text-cyan-400">
                FACE DETECTED | CONF: {(faceInfo.confidence * 100).toFixed(0)}%
              </div>
            </div>
          )}
        </div>

        {/* HEX data feed */}
        <div className="font-mono text-[8px] text-cyan-900/60 mb-4 overflow-hidden h-3">
          {scanning && (
            <motion.div
              animate={{ x: [0, -200] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="whitespace-nowrap"
            >
              0x4A415256 0x49530000 0xBIOMETRIC 0xSCAN0001 0xFACE_ID 0xVERIFY 0xNEURAL_LINK 0xACTIVE
            </motion.div>
          )}
        </div>

        {/* Status */}
        <p className={`font-mono text-[10px] tracking-[0.12em] mb-6 ${
          granted ? 'text-green-400' : scanning ? 'text-cyan-400' : 'text-cyan-300/60'
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

        {/* Retry after failure */}
        {!scanning && !granted && faceInfo && !faceInfo.detected && (
          <p className="mt-3 text-[9px] text-amber-400/60 font-mono">
            Position your face within the frame and try again
          </p>
        )}
      </motion.div>
    </div>
  );
}
