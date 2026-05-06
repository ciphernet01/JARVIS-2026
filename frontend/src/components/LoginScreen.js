import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Scan, ShieldCheck } from 'lucide-react';

export default function LoginScreen({ onLogin, api }) {
  const [status, setStatus] = useState('AWAITING BIOMETRIC INPUT');
  const [scanning, setScanning] = useState(false);
  const [granted, setGranted] = useState(false);

  const startScan = async () => {
    setScanning(true);
    setStatus('SCANNING BIOMETRICS...');

    // Simulate scan delay
    await new Promise(r => setTimeout(r, 2500));

    try {
      const resp = await fetch(`${api}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: 'biometric' }),
      });
      const data = await resp.json();

      if (data.success) {
        setStatus('ACCESS GRANTED');
        setGranted(true);
        setTimeout(() => onLogin(data.token), 1500);
      } else {
        setStatus('ACCESS DENIED');
        setScanning(false);
      }
    } catch (e) {
      setStatus('NEURAL LINK ERROR');
      setScanning(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" data-testid="login-screen">
      {/* Background */}
      <div className="absolute inset-0 bg-slate-950">
        <div className="absolute inset-0 opacity-20" style={{
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
        className="relative z-10 text-center p-12 border border-cyan-500/30 bg-slate-950/80 backdrop-blur-xl"
        data-testid="login-container"
      >
        {/* Title */}
        <h1 className="font-display text-4xl tracking-tighter uppercase text-cyan-400 mb-1" style={{ textShadow: '0 0 20px rgba(6,182,212,0.5)' }}>
          J.A.R.V.I.S
        </h1>
        <p className="font-display text-xs tracking-[0.2em] uppercase text-cyan-300/60 mb-10">
          Neural Interface Security Protocol
        </p>

        {/* Scanner Box */}
        <div className="relative w-48 h-48 mx-auto mb-8 border border-cyan-500/40 overflow-hidden">
          {/* Corners */}
          <div className="absolute top-2 left-2 w-4 h-4 border-t border-l border-cyan-400" />
          <div className="absolute top-2 right-2 w-4 h-4 border-t border-r border-cyan-400" />
          <div className="absolute bottom-2 left-2 w-4 h-4 border-b border-l border-cyan-400" />
          <div className="absolute bottom-2 right-2 w-4 h-4 border-b border-r border-cyan-400" />

          {/* Face mesh placeholder */}
          <div className="absolute inset-0 flex items-center justify-center">
            <Scan className="w-20 h-20 text-cyan-400/40" />
          </div>

          {/* Scan line */}
          {scanning && (
            <motion.div
              className="absolute left-0 right-0 h-0.5 bg-cyan-400"
              style={{ boxShadow: '0 0 10px #06b6d4, 0 0 20px #06b6d4' }}
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            />
          )}

          {/* Granted overlay */}
          {granted && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="absolute inset-0 bg-green-500/20 flex items-center justify-center"
            >
              <ShieldCheck className="w-16 h-16 text-green-400" />
            </motion.div>
          )}
        </div>

        {/* Status */}
        <p className={`font-mono text-xs tracking-[0.15em] mb-6 ${
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
            Initialize Bio-Scan
          </motion.button>
        )}
      </motion.div>
    </div>
  );
}
