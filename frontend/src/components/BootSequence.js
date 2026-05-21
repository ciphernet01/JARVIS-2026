import React, { useEffect, useMemo, useState } from 'react';

const DEFAULT_STEPS = [
  'Initializing Neural Interface Core',
  'Calibrating Sensor Array',
  'Loading Voice Cognition Stack',
  'Syncing Memory Lattice',
  'Establishing Secure Channels',
  'Mapping System Modules',
  'Verifying Diagnostics',
  'Bootstrapping Command Matrix',
  'Activating A.S.T.R.A Shell',
];

export default function BootSequence({ onComplete, durationMs = 3200 }) {
  const steps = useMemo(() => DEFAULT_STEPS, []);
  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const stepInterval = Math.max(200, Math.floor(durationMs / steps.length));
    const progressInterval = Math.max(40, Math.floor(durationMs / 80));

    const stepTimer = setInterval(() => {
      setIndex((prev) => Math.min(prev + 1, steps.length - 1));
    }, stepInterval);

    const progressTimer = setInterval(() => {
      setProgress((prev) => Math.min(prev + 2, 100));
    }, progressInterval);

    const doneTimer = setTimeout(() => {
      onComplete();
    }, durationMs + 200);

    return () => {
      clearInterval(stepTimer);
      clearInterval(progressTimer);
      clearTimeout(doneTimer);
    };
  }, [durationMs, onComplete, steps.length]);

  return (
    <div className="boot-overlay" role="presentation">
      <div className="boot-scan" />
      <div className="boot-shell">
        <div className="boot-header">
          <span className="boot-title">A.S.T.R.A BIOS</span>
          <span className="boot-subtitle">Spatial Interface v2026.05</span>
        </div>
        <div className="boot-grid">
          <div className="boot-left">
            <div className="boot-log">
              {steps.slice(0, index + 1).map((step, i) => (
                <div key={`${step}-${i}`} className="boot-line">
                  <span className="boot-prefix">{String(i + 1).padStart(2, '0')}</span>
                  <span className="boot-text">{step}</span>
                  <span className="boot-ok">OK</span>
                </div>
              ))}
              <div className="boot-cursor" />
            </div>
          </div>
          <div className="boot-right">
            <div className="boot-telemetry">
              <div className="boot-label">System Matrix</div>
              <div className="boot-panel">
                <div className="boot-meter">
                  <span>CPU</span>
                  <div className="boot-bar"><div style={{ width: `${Math.min(progress + 10, 100)}%` }} /></div>
                </div>
                <div className="boot-meter">
                  <span>MEM</span>
                  <div className="boot-bar"><div style={{ width: `${Math.min(progress + 22, 100)}%` }} /></div>
                </div>
                <div className="boot-meter">
                  <span>NET</span>
                  <div className="boot-bar"><div style={{ width: `${Math.min(progress + 35, 100)}%` }} /></div>
                </div>
              </div>
            </div>
            <div className="boot-telemetry">
              <div className="boot-label">Boot Progress</div>
              <div className="boot-progress">
                <div className="boot-progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <div className="boot-percent">{progress}%</div>
            </div>
          </div>
        </div>
        <div className="boot-footer">Press any key to enter command layer</div>
      </div>
    </div>
  );
}
