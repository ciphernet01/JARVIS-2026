import React, { useCallback, useState, useRef, useEffect } from 'react';
import { Camera, ShieldCheck, UserCheck, AlertCircle, RefreshCw, LifeBuoy, Lock, DatabaseBackup, History, Package, Search, Play, RotateCcw, Terminal, Languages, SlidersHorizontal, ShieldAlert, Activity } from 'lucide-react';
import VoiceTrainingWizard from './VoiceTrainingWizard';

async function readResponse(resp) {
  const text = await resp.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

export default function SettingsPanel({ api, token, preferences, onPreferencesChange }) {
  const [cameraActive, setCameraActive] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollStatus, setEnrollStatus] = useState(null);
  const [enrolledFaces, setEnrolledFaces] = useState(0);
  const [safety, setSafety] = useState(null);
  const [auditEntries, setAuditEntries] = useState([]);
  const [checkpoints, setCheckpoints] = useState([]);
  const [safetyBusy, setSafetyBusy] = useState(false);
  const [safetyStatus, setSafetyStatus] = useState(null);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState('');
  const [restorePlan, setRestorePlan] = useState(null);
  const [maintenanceCommand, setMaintenanceCommand] = useState('list-root');
  const [maintenanceResult, setMaintenanceResult] = useState(null);
  const [packageState, setPackageState] = useState(null);
  const [packageQuery, setPackageQuery] = useState('');
  const [packagePlan, setPackagePlan] = useState(null);
  const [packageResult, setPackageResult] = useState(null);
  const [packageBusy, setPackageBusy] = useState(false);
  const [preferenceState, setPreferenceState] = useState(null);
  const [preferenceCaps, setPreferenceCaps] = useState(null);
  const [preferenceStatus, setPreferenceStatus] = useState(null);
  const [preferenceBusy, setPreferenceBusy] = useState(false);
  const [securityReport, setSecurityReport] = useState(null);
  const [securityReports, setSecurityReports] = useState([]);
  const [securityBusy, setSecurityBusy] = useState(false);
  const [securityStatus, setSecurityStatus] = useState(null);
  const [performanceReport, setPerformanceReport] = useState(null);
  const [performanceReports, setPerformanceReports] = useState([]);
  const [performanceBusy, setPerformanceBusy] = useState(false);
  const [performanceStatus, setPerformanceStatus] = useState(null);
  const [failoverReport, setFailoverReport] = useState(null);
  const [failoverReports, setFailoverReports] = useState([]);
  const [failoverBusy, setFailoverBusy] = useState(false);
  const [failoverStatus, setFailoverStatus] = useState(null);
  const [releaseBundle, setReleaseBundle] = useState(null);
  const [releaseBundles, setReleaseBundles] = useState([]);
  const [releaseBusy, setReleaseBusy] = useState(false);
  const [releaseStatus, setReleaseStatus] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const activePreferences = preferenceState || preferences || {};

  const refreshSafety = useCallback(async () => {
    try {
      const [safetyResp, auditResp, checkpointsResp] = await Promise.all([
        fetch(`${api}/api/os/safety/state`, {
          headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
        }),
        fetch(`${api}/api/os/audit/recent?limit=6`, {
          headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
        }),
        fetch(`${api}/api/os/safety/checkpoints?limit=6`, {
          headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
        }),
      ]);
      const safetyData = await readResponse(safetyResp);
      const auditData = await readResponse(auditResp);
      const checkpointsData = await readResponse(checkpointsResp);
      if (safetyResp.ok) setSafety(safetyData.state);
      if (auditResp.ok) setAuditEntries(auditData.entries || []);
      if (checkpointsResp.ok) {
        const nextCheckpoints = checkpointsData.checkpoints || [];
        setCheckpoints(nextCheckpoints);
        setSelectedCheckpoint(prev => prev || nextCheckpoints[0]?.id || '');
      }
    } catch (e) {
      setSafetyStatus({ success: false, message: `Safety telemetry unavailable: ${e.message}` });
    }
  }, [api, token]);

  const refreshPackageState = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/packages/state`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (resp.ok) setPackageState(data.package_manager);
    } catch (e) {
      setPackageResult({ success: false, message: `Package manager unavailable: ${e.message}` });
    }
  }, [api, token]);

  const refreshPreferences = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/preferences`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Preference sync failed');
      setPreferenceState(data.preferences);
      setPreferenceCaps(data.capabilities);
      onPreferencesChange?.(data.preferences);
    } catch (e) {
      setPreferenceStatus({ success: false, message: `Preference sync failed: ${e.message}` });
    }
  }, [api, token, onPreferencesChange]);

  const refreshSecurityReports = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/security/audits?limit=5`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (resp.ok) setSecurityReports(data.reports || []);
    } catch (e) {
      setSecurityStatus({ success: false, message: `Security audit reports unavailable: ${e.message}` });
    }
  }, [api, token]);

  const refreshPerformanceReports = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/performance/baselines?limit=5`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (resp.ok) setPerformanceReports(data.reports || []);
    } catch (e) {
      setPerformanceStatus({ success: false, message: `Performance reports unavailable: ${e.message}` });
    }
  }, [api, token]);

  const refreshFailoverReports = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/failover/drills?limit=5`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (resp.ok) setFailoverReports(data.reports || []);
    } catch (e) {
      setFailoverStatus({ success: false, message: `Failover drill reports unavailable: ${e.message}` });
    }
  }, [api, token]);

  const refreshReleaseBundles = useCallback(async () => {
    try {
      const resp = await fetch(`${api}/api/os/release/evidence?limit=5`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (resp.ok) setReleaseBundles(data.bundles || []);
    } catch (e) {
      setReleaseStatus({ success: false, message: `Release evidence unavailable: ${e.message}` });
    }
  }, [api, token]);

  useEffect(() => {
    refreshSafety();
    refreshPackageState();
    refreshPreferences();
    refreshSecurityReports();
    refreshPerformanceReports();
    refreshFailoverReports();
    refreshReleaseBundles();
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, [refreshSafety, refreshPackageState, refreshPreferences, refreshSecurityReports, refreshPerformanceReports, refreshFailoverReports, refreshReleaseBundles]);

  const runSecurityAudit = async () => {
    setSecurityBusy(true);
    setSecurityStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/security/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ save: true }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Security audit failed');
      setSecurityReport(data.report);
      setSecurityStatus({ success: data.report?.overall_status !== 'fail', message: `Security audit ${data.report?.overall_status || 'complete'} / score ${Math.round((data.report?.score || 0) * 100)}%.` });
      await refreshSecurityReports();
      await refreshSafety();
    } catch (e) {
      setSecurityStatus({ success: false, message: `Security audit failed: ${e.message}` });
    } finally {
      setSecurityBusy(false);
    }
  };

  const runPerformanceBaseline = async () => {
    setPerformanceBusy(true);
    setPerformanceStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/performance/baseline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ label: 'settings-baseline', duration_seconds: 5, interval_seconds: 1, save: true }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Performance baseline failed');
      setPerformanceReport(data.report);
      const growth = data.report?.summary?.rss_growth_mb ?? 0;
      setPerformanceStatus({ success: data.report?.overall_status !== 'fail', message: `Performance baseline ${data.report?.overall_status || 'complete'} / memory growth ${growth} MB.` });
      await refreshPerformanceReports();
    } catch (e) {
      setPerformanceStatus({ success: false, message: `Performance baseline failed: ${e.message}` });
    } finally {
      setPerformanceBusy(false);
    }
  };

  const runFailoverDrill = async () => {
    setFailoverBusy(true);
    setFailoverStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/failover/drill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ label: 'settings-failover-drill', save: true }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Failover drill failed');
      setFailoverReport(data.report);
      setFailoverStatus({ success: data.report?.overall_status !== 'fail', message: `Failover drill ${data.report?.overall_status || 'complete'} / score ${Math.round((data.report?.score || 0) * 100)}%.` });
      await refreshFailoverReports();
      await refreshSafety();
    } catch (e) {
      setFailoverStatus({ success: false, message: `Failover drill failed: ${e.message}` });
    } finally {
      setFailoverBusy(false);
    }
  };

  const createReleaseEvidence = async () => {
    setReleaseBusy(true);
    setReleaseStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/release/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ label: 'settings-release-evidence', save: true }),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Release evidence bundle failed');
      setReleaseBundle(data.bundle);
      setReleaseStatus({ success: data.bundle?.release_status !== 'blocked', message: `Release evidence ${data.bundle?.release_status || 'created'} / score ${Math.round((data.bundle?.score || 0) * 100)}%.` });
      await refreshReleaseBundles();
    } catch (e) {
      setReleaseStatus({ success: false, message: `Release evidence failed: ${e.message}` });
    } finally {
      setReleaseBusy(false);
    }
  };

  const updatePreferences = async (changes) => {
    setPreferenceBusy(true);
    setPreferenceStatus(null);
    const optimistic = { ...activePreferences, ...changes };
    setPreferenceState(optimistic);
    onPreferencesChange?.(optimistic);
    try {
      const resp = await fetch(`${api}/api/os/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify(changes),
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Preference update failed');
      setPreferenceState(data.preferences);
      setPreferenceCaps(data.capabilities);
      onPreferencesChange?.(data.preferences);
      setPreferenceStatus({ success: true, message: data.message || 'OS preferences updated.' });
    } catch (e) {
      setPreferenceStatus({ success: false, message: `Preference update failed: ${e.message}` });
      await refreshPreferences();
    } finally {
      setPreferenceBusy(false);
    }
  };

  const resetPreferences = async () => {
    setPreferenceBusy(true);
    setPreferenceStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/preferences/reset`, {
        method: 'POST',
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await readResponse(resp);
      if (!resp.ok) throw new Error(data.detail || data.message || 'Preference reset failed');
      setPreferenceState(data.preferences);
      setPreferenceCaps(data.capabilities);
      onPreferencesChange?.(data.preferences);
      setPreferenceStatus({ success: true, message: data.message || 'OS preferences reset.' });
    } catch (e) {
      setPreferenceStatus({ success: false, message: `Preference reset failed: ${e.message}` });
    } finally {
      setPreferenceBusy(false);
    }
  };

  const packageAction = async (action, dryRun = true) => {
    const packageName = packageQuery.trim();
    if (!packageName && action !== 'update') return;
    setPackageBusy(true);
    setPackageResult(null);
    try {
      const resp = await fetch(`${api}/api/os/packages/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({
          action,
          package: packageName || null,
          dry_run: dryRun,
          confirmed: !dryRun,
        }),
      });
      const data = await readResponse(resp);
      if (dryRun && data.plan) setPackagePlan({ ...data.plan, message: data.message });
      setPackageResult({ success: resp.ok && data.success, message: data.message || 'Package action completed.', stdout: data.stdout, stderr: data.stderr });
      await refreshSafety();
      await refreshPackageState();
    } catch (e) {
      setPackageResult({ success: false, message: `Package action failed: ${e.message}` });
    } finally {
      setPackageBusy(false);
    }
  };

  const searchPackages = async () => {
    const query = packageQuery.trim();
    if (!query) return;
    setPackageBusy(true);
    setPackageResult(null);
    try {
      const resp = await fetch(`${api}/api/os/packages/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ query }),
      });
      const data = await readResponse(resp);
      setPackageResult({ success: resp.ok && data.success, message: data.message || 'Search complete.', stdout: data.stdout, stderr: data.stderr });
    } catch (e) {
      setPackageResult({ success: false, message: `Package search failed: ${e.message}` });
    } finally {
      setPackageBusy(false);
    }
  };

  const updateSafetyMode = async (endpoint, enabled) => {
    setSafetyBusy(true);
    setSafetyStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/safety/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ enabled, reason: 'settings panel toggle' }),
      });
      const data = await readResponse(resp);
      setSafetyStatus({ success: resp.ok, message: data.message || (resp.ok ? 'Safety state updated.' : 'Safety update failed.') });
      if (data.state) setSafety(data.state);
      await refreshSafety();
    } catch (e) {
      setSafetyStatus({ success: false, message: `Safety update failed: ${e.message}` });
    } finally {
      setSafetyBusy(false);
    }
  };

  const createCheckpoint = async () => {
    setSafetyBusy(true);
    setSafetyStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/safety/checkpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ label: 'settings-panel-checkpoint', notes: 'Created before safety-sensitive roadmap work.' }),
      });
      const data = await readResponse(resp);
      setSafetyStatus({ success: resp.ok, message: data.message || (resp.ok ? 'Checkpoint created.' : 'Checkpoint failed.') });
      if (data.state) setSafety(data.state);
      await refreshSafety();
    } catch (e) {
      setSafetyStatus({ success: false, message: `Checkpoint failed: ${e.message}` });
    } finally {
      setSafetyBusy(false);
    }
  };

  const restoreCheckpoint = async (dryRun = true) => {
    if (!selectedCheckpoint) return;
    setSafetyBusy(true);
    setSafetyStatus(null);
    try {
      const resp = await fetch(`${api}/api/os/safety/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ checkpoint_id: selectedCheckpoint, dry_run: dryRun, confirmed: !dryRun }),
      });
      const data = await readResponse(resp);
      setRestorePlan(data.data || null);
      setSafetyStatus({ success: resp.ok && data.success !== false, message: data.message || 'Restore request completed.' });
      if (data.state) setSafety(data.state);
      await refreshSafety();
    } catch (e) {
      setSafetyStatus({ success: false, message: `Restore failed: ${e.message}` });
    } finally {
      setSafetyBusy(false);
    }
  };

  const runMaintenanceCommand = async () => {
    const command = maintenanceCommand.trim();
    if (!command) return;
    setSafetyBusy(true);
    setMaintenanceResult(null);
    try {
      const resp = await fetch(`${api}/api/os/safety/maintenance-command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-JARVIS-TOKEN': token },
        body: JSON.stringify({ command, timeout_seconds: 20 }),
      });
      const data = await readResponse(resp);
      setMaintenanceResult({ success: resp.ok && data.success, ...data });
      await refreshSafety();
    } catch (e) {
      setMaintenanceResult({ success: false, message: `Maintenance command failed: ${e.message}` });
    } finally {
      setSafetyBusy(false);
    }
  };

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

      <VoiceTrainingWizard api={api} token={token} />

      {/* Language & Accessibility */}
      <div className="border border-cyan-900/50 p-4 mb-4">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 flex items-center gap-2">
            <Languages size={14} /> Language & Accessibility
          </h3>
          <button
            onClick={resetPreferences}
            disabled={preferenceBusy}
            className="flex items-center gap-2 px-3 py-1.5 border border-amber-500/40 text-amber-300 font-display text-[9px] tracking-wider uppercase hover:bg-amber-950/20 disabled:opacity-40"
            data-testid="preferences-reset"
          >
            <RotateCcw size={11} /> Reset
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2">Interface Language</div>
            <select
              value={activePreferences.language || 'en-US'}
              onChange={(e) => updatePreferences({ language: e.target.value })}
              className="w-full bg-black/50 border border-cyan-900/40 px-2 py-2 text-[10px] font-mono text-cyan-100 focus:border-cyan-500/60 focus:outline-none"
              data-testid="preferences-language"
            >
              {(preferenceCaps?.languages || [{ code: 'en-US', label: 'English (US)' }]).map((item) => (
                <option key={item.code} value={item.code}>{item.label}</option>
              ))}
            </select>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2">Voice Style</div>
            <select
              value={activePreferences.tts_voice || 'system'}
              onChange={(e) => updatePreferences({ tts_voice: e.target.value })}
              className="w-full bg-black/50 border border-cyan-900/40 px-2 py-2 text-[10px] font-mono text-cyan-100 focus:border-cyan-500/60 focus:outline-none"
              data-testid="preferences-tts-voice"
            >
              {(preferenceCaps?.tts_voices || ['system']).map((voice) => (
                <option key={voice} value={voice}>{voice.replaceAll('-', ' ')}</option>
              ))}
            </select>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2 flex items-center gap-1">
              <SlidersHorizontal size={10} /> Telemetry Refresh
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-3 items-center">
              <input
                type="range"
                min={preferenceCaps?.telemetry_refresh_range?.min || 3}
                max={preferenceCaps?.telemetry_refresh_range?.max || 30}
                step="1"
                value={activePreferences.telemetry_refresh_seconds || 5}
                onChange={(e) => setPreferenceState({ ...activePreferences, telemetry_refresh_seconds: parseInt(e.target.value, 10) })}
                onMouseUp={(e) => updatePreferences({ telemetry_refresh_seconds: parseInt(e.currentTarget.value, 10) })}
                onTouchEnd={(e) => updatePreferences({ telemetry_refresh_seconds: parseInt(e.currentTarget.value, 10) })}
                className="accent-cyan-400"
                data-testid="preferences-refresh"
              />
              <span className="font-mono text-xs text-cyan-100">{activePreferences.telemetry_refresh_seconds || 5}s</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2 mb-3">
          {[
            ['high_contrast', 'High Contrast'],
            ['large_text', 'Large Text'],
            ['reduced_motion', 'Reduced Motion'],
            ['scanlines', 'Scanlines'],
          ].map(([key, label]) => (
            <label
              key={key}
              className={`flex cursor-pointer items-center justify-between gap-2 border px-3 py-2 font-display text-[9px] tracking-wider uppercase transition-all ${
                activePreferences[key] ? 'border-cyan-400/60 bg-cyan-950/30 text-cyan-100' : 'border-cyan-900/30 bg-slate-950/40 text-cyan-300/50'
              }`}
              data-testid={`preferences-${key}`}
            >
              <span>{label}</span>
              <input
                type="checkbox"
                checked={Boolean(activePreferences[key])}
                onChange={(e) => updatePreferences({ [key]: e.target.checked })}
                className="accent-cyan-400"
              />
            </label>
          ))}
        </div>

        {preferenceStatus && (
          <div className={`flex items-start gap-2 p-3 border ${
            preferenceStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
          }`} data-testid="preferences-status">
            {preferenceStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
            <span className="font-mono text-[10px]">{preferenceStatus.message}</span>
          </div>
        )}
      </div>

      {/* Recovery & Safety */}
      <div className="border border-cyan-900/50 p-4 mb-4">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 flex items-center gap-2">
            <LifeBuoy size={14} /> Recovery & Safety
          </h3>
          <button
            onClick={refreshSafety}
            disabled={safetyBusy}
            className="flex items-center gap-2 px-3 py-1.5 border border-cyan-900/40 text-cyan-300/60 font-display text-[9px] tracking-wider uppercase hover:text-cyan-300 hover:border-cyan-500/50 disabled:opacity-40"
            data-testid="safety-refresh-btn"
          >
            <RefreshCw size={11} /> Refresh
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Safe Mode</div>
            <div className={`font-mono text-sm ${safety?.safe_mode ? 'text-amber-300' : 'text-green-400'}`}>
              {safety?.safe_mode ? 'Enabled' : 'Normal'}
            </div>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Recovery</div>
            <div className={`font-mono text-sm ${safety?.recovery_mode ? 'text-amber-300' : 'text-cyan-100'}`}>
              {safety?.recovery_mode ? 'Active' : 'Standby'}
            </div>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Checkpoints</div>
            <div className="font-mono text-sm text-cyan-100">{safety?.checkpoint_count ?? '-'}</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-4">
          <button
            onClick={() => updateSafetyMode('safe-mode', !safety?.safe_mode)}
            disabled={safetyBusy}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-amber-500/40 text-amber-300 font-display text-[9px] tracking-wider uppercase hover:bg-amber-950/20 disabled:opacity-40"
            data-testid="safe-mode-toggle"
          >
            <Lock size={12} /> {safety?.safe_mode ? 'Disable Safe' : 'Enable Safe'}
          </button>
          <button
            onClick={() => updateSafetyMode('recovery-mode', !safety?.recovery_mode)}
            disabled={safetyBusy}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="recovery-mode-toggle"
          >
            <LifeBuoy size={12} /> {safety?.recovery_mode ? 'Exit Recovery' : 'Recovery Mode'}
          </button>
          <button
            onClick={createCheckpoint}
            disabled={safetyBusy}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-green-500/40 text-green-300 font-display text-[9px] tracking-wider uppercase hover:bg-green-950/20 disabled:opacity-40"
            data-testid="checkpoint-create-btn"
          >
            <DatabaseBackup size={12} /> Checkpoint
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2">Restore Checkpoint</div>
            <select
              value={selectedCheckpoint}
              onChange={(e) => setSelectedCheckpoint(e.target.value)}
              className="w-full bg-black/50 border border-cyan-900/40 px-2 py-2 text-[10px] font-mono text-cyan-100 mb-2 focus:border-cyan-500/60 focus:outline-none"
              data-testid="checkpoint-select"
            >
              {checkpoints.length === 0 ? (
                <option value="">No checkpoints</option>
              ) : (
                checkpoints.map((checkpoint) => (
                  <option key={checkpoint.id} value={checkpoint.id}>{checkpoint.label}</option>
                ))
              )}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => restoreCheckpoint(true)}
                disabled={safetyBusy || !selectedCheckpoint}
                className="flex items-center justify-center gap-2 px-2 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[8px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
                data-testid="restore-plan-btn"
              >
                <RotateCcw size={11} /> Plan
              </button>
              <button
                onClick={() => restoreCheckpoint(false)}
                disabled={safetyBusy || !restorePlan || restorePlan.checkpoint_id !== selectedCheckpoint}
                className="flex items-center justify-center gap-2 px-2 py-2 border border-amber-500/40 text-amber-300 font-display text-[8px] tracking-wider uppercase hover:bg-amber-950/20 disabled:opacity-40"
                data-testid="restore-execute-btn"
              >
                <ShieldCheck size={11} /> Restore
              </button>
            </div>
            {restorePlan?.plan && (
              <div className="mt-2 font-mono text-[9px] text-cyan-300/45">
                {restorePlan.plan.length} file(s) staged for restore.
              </div>
            )}
          </div>

          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-2">Maintenance Shell</div>
            <div className="flex gap-2 mb-2">
              <select
                value={maintenanceCommand}
                onChange={(e) => setMaintenanceCommand(e.target.value)}
                className="flex-1 bg-black/50 border border-cyan-900/40 px-2 py-2 text-[10px] font-mono text-cyan-100 focus:border-cyan-500/60 focus:outline-none"
                data-testid="maintenance-command-select"
              >
                {(safety?.maintenance_allowlist || ['list-root', 'pwd']).map((command) => (
                  <option key={command} value={command}>{command}</option>
                ))}
              </select>
              <button
                onClick={runMaintenanceCommand}
                disabled={safetyBusy || !maintenanceCommand.trim()}
                className="flex items-center justify-center gap-2 px-3 py-2 border border-green-500/40 text-green-300 font-display text-[8px] tracking-wider uppercase hover:bg-green-950/20 disabled:opacity-40"
                data-testid="maintenance-run-btn"
              >
                <Terminal size={11} /> Run
              </button>
            </div>
            {maintenanceResult && (
              <pre className={`max-h-24 overflow-y-auto whitespace-pre-wrap font-mono text-[9px] ${maintenanceResult.success ? 'text-cyan-100/70' : 'text-red-300'}`}>
                {(maintenanceResult.stdout || maintenanceResult.stderr || maintenanceResult.message || '').slice(0, 900)}
              </pre>
            )}
          </div>
        </div>

        {safetyStatus && (
          <div className={`mb-4 flex items-start gap-2 p-3 border ${
            safetyStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
          }`} data-testid="safety-status">
            {safetyStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
            <span className="font-mono text-[10px]">{safetyStatus.message}</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="font-display text-[8px] tracking-widest text-cyan-300/40 uppercase mb-2">Safety Gates</div>
            <div className="space-y-1">
              {(safety?.safety_gates || []).slice(0, 6).map((gate) => (
                <div key={gate} className="font-mono text-[9px] text-cyan-300/45">- {gate.replaceAll('_', ' ')}</div>
              ))}
            </div>
          </div>
          <div>
            <div className="font-display text-[8px] tracking-widest text-cyan-300/40 uppercase mb-2 flex items-center gap-1">
              <History size={10} /> Recent Audit
            </div>
            <div className="space-y-1">
              {auditEntries.length === 0 ? (
                <div className="font-mono text-[9px] text-cyan-300/30">No audit entries yet.</div>
              ) : (
                auditEntries.map((entry) => (
                  <div key={entry.id} className="font-mono text-[9px] text-cyan-300/45 truncate">
                    {entry.action} / {entry.success ? 'ok' : 'blocked'}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Package Lifecycle */}
      <div className="border border-cyan-900/50 p-4 mb-4">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 flex items-center gap-2">
            <Package size={14} /> Package Lifecycle
          </h3>
          <span className={`font-mono text-[9px] ${packageState?.available ? 'text-green-400' : 'text-amber-400'}`}>
            {packageState?.available ? `${packageState.provider?.name} ready` : 'provider unavailable'}
          </span>
        </div>

        <div className="flex gap-2 mb-3">
          <input
            value={packageQuery}
            onChange={(e) => setPackageQuery(e.target.value)}
            placeholder="Package id, e.g. Microsoft.VisualStudioCode"
            className="flex-1 bg-black/50 border border-cyan-900/40 px-3 py-2 text-xs font-mono text-cyan-100 placeholder-cyan-900 focus:border-cyan-500/60 focus:outline-none"
            data-testid="package-query"
          />
          <button
            onClick={searchPackages}
            disabled={packageBusy || !packageQuery.trim() || !packageState?.available}
            className="flex items-center gap-2 px-3 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="package-search-btn"
          >
            <Search size={12} /> Search
          </button>
        </div>

        <div className="grid grid-cols-4 gap-2 mb-3">
          <button
            onClick={() => packageAction('install', true)}
            disabled={packageBusy || !packageQuery.trim() || !packageState?.available}
            className="px-3 py-2 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="package-plan-install"
          >
            Plan Install
          </button>
          <button
            onClick={() => packageAction('uninstall', true)}
            disabled={packageBusy || !packageQuery.trim() || !packageState?.available}
            className="px-3 py-2 border border-red-500/40 text-red-300 font-display text-[9px] tracking-wider uppercase hover:bg-red-950/20 disabled:opacity-40"
            data-testid="package-plan-uninstall"
          >
            Plan Remove
          </button>
          <button
            onClick={() => packageAction('update', true)}
            disabled={packageBusy || !packageState?.available}
            className="px-3 py-2 border border-amber-500/40 text-amber-300 font-display text-[9px] tracking-wider uppercase hover:bg-amber-950/20 disabled:opacity-40"
            data-testid="package-plan-update"
          >
            Plan Update
          </button>
          <button
            onClick={() => packageAction(packagePlan?.action || 'install', false)}
            disabled={packageBusy || !packagePlan || packagePlan.blocked || !packageState?.available}
            className="flex items-center justify-center gap-2 px-3 py-2 border border-green-500/40 text-green-300 font-display text-[9px] tracking-wider uppercase hover:bg-green-950/20 disabled:opacity-40"
            data-testid="package-execute"
          >
            <Play size={11} /> Execute
          </button>
        </div>

        {packagePlan && (
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3 mb-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Execution Plan</div>
            <div className="font-mono text-[9px] text-cyan-100 break-all">{packagePlan.command?.join(' ') || 'No command generated'}</div>
            <div className="mt-2 font-mono text-[9px] text-cyan-300/45">
              {packagePlan.blocked ? `Blocked: ${packagePlan.reason}` : 'Requires explicit execute confirmation.'}
            </div>
          </div>
        )}

        {packageResult && (
          <div className={`border p-3 ${packageResult.success ? 'border-green-500/30 bg-green-950/20' : 'border-red-500/30 bg-red-950/20'}`} data-testid="package-result">
            <div className={`font-mono text-[10px] ${packageResult.success ? 'text-green-300' : 'text-red-300'}`}>{packageResult.message}</div>
            {(packageResult.stdout || packageResult.stderr) && (
              <pre className="mt-2 max-h-36 overflow-y-auto whitespace-pre-wrap font-mono text-[9px] text-cyan-100/70">
                {(packageResult.stdout || packageResult.stderr || '').slice(0, 1600)}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Production Hardening */}
      <div className="border border-cyan-900/50 p-4 mb-4">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 flex items-center gap-2">
            <ShieldAlert size={14} /> Production Hardening
          </h3>
          <button
            onClick={runSecurityAudit}
            disabled={securityBusy}
            className="flex items-center gap-2 px-3 py-1.5 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
            data-testid="security-audit-run"
          >
            {securityBusy ? <RefreshCw size={11} className="animate-spin" /> : <ShieldCheck size={11} />}
            Run Audit
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Latest Status</div>
            <div className={`font-mono text-sm ${
              securityReport?.overall_status === 'pass' ? 'text-green-400' :
              securityReport?.overall_status === 'fail' ? 'text-red-300' :
              'text-amber-300'
            }`}>
              {securityReport?.overall_status || securityReports[0]?.overall_status || 'Not Run'}
            </div>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Score</div>
            <div className="font-mono text-sm text-cyan-100">
              {Math.round(((securityReport?.score ?? securityReports[0]?.score) || 0) * 100)}%
            </div>
          </div>
          <div className="border border-cyan-900/30 bg-slate-950/40 p-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Reports</div>
            <div className="font-mono text-sm text-cyan-100">{securityReports.length}</div>
          </div>
        </div>

        {securityReport?.checks && (
          <div className="grid grid-cols-2 gap-2 mb-3">
            {securityReport.checks.map((check) => (
              <div key={check.key} className={`border p-3 ${
                check.status === 'pass' ? 'border-green-500/25 bg-green-950/10' :
                check.status === 'fail' ? 'border-red-500/30 bg-red-950/20' :
                'border-amber-500/25 bg-amber-950/10'
              }`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-display text-[8px] tracking-widest uppercase text-cyan-300/45">{check.label}</span>
                  <span className={`font-mono text-[8px] uppercase ${
                    check.status === 'pass' ? 'text-green-300' :
                    check.status === 'fail' ? 'text-red-300' :
                    'text-amber-300'
                  }`}>{check.status}</span>
                </div>
                <div className="font-mono text-[9px] text-cyan-100/70">{check.detail}</div>
                {check.recommendation && (
                  <div className="mt-2 font-mono text-[8px] text-cyan-300/40">{check.recommendation}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {securityStatus && (
          <div className={`flex items-start gap-2 p-3 border ${
            securityStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
          }`} data-testid="security-audit-status">
            {securityStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
            <span className="font-mono text-[10px]">{securityStatus.message}</span>
          </div>
        )}

        <div className="mt-4 border border-cyan-900/35 bg-slate-950/30 p-3">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/45 flex items-center gap-2">
              <Activity size={12} /> Performance Baseline
            </div>
            <button
              onClick={runPerformanceBaseline}
              disabled={performanceBusy}
              className="flex items-center gap-2 px-3 py-1.5 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
              data-testid="performance-baseline-run"
            >
              {performanceBusy ? <RefreshCw size={11} className="animate-spin" /> : <Activity size={11} />}
              Run 5s
            </button>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Status</div>
              <div className={`font-mono text-sm ${
                performanceReport?.overall_status === 'pass' ? 'text-green-400' :
                performanceReport?.overall_status === 'fail' ? 'text-red-300' :
                'text-amber-300'
              }`}>
                {performanceReport?.overall_status || performanceReports[0]?.overall_status || 'Not Run'}
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">RSS Growth</div>
              <div className="font-mono text-sm text-cyan-100">
                {(performanceReport?.summary?.rss_growth_mb ?? performanceReports[0]?.summary?.rss_growth_mb ?? 0)} MB
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Reports</div>
              <div className="font-mono text-sm text-cyan-100">{performanceReports.length}</div>
            </div>
          </div>

          {performanceStatus && (
            <div className={`mt-3 flex items-start gap-2 p-3 border ${
              performanceStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
            }`} data-testid="performance-baseline-status">
              {performanceStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
              <span className="font-mono text-[10px]">{performanceStatus.message}</span>
            </div>
          )}
        </div>

        <div className="mt-4 border border-cyan-900/35 bg-slate-950/30 p-3">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/45 flex items-center gap-2">
              <LifeBuoy size={12} /> Failover Drill
            </div>
            <button
              onClick={runFailoverDrill}
              disabled={failoverBusy}
              className="flex items-center gap-2 px-3 py-1.5 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
              data-testid="failover-drill-run"
            >
              {failoverBusy ? <RefreshCw size={11} className="animate-spin" /> : <LifeBuoy size={11} />}
              Run Drill
            </button>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Status</div>
              <div className={`font-mono text-sm ${
                failoverReport?.overall_status === 'pass' ? 'text-green-400' :
                failoverReport?.overall_status === 'fail' ? 'text-red-300' :
                'text-amber-300'
              }`}>
                {failoverReport?.overall_status || failoverReports[0]?.overall_status || 'Not Run'}
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Score</div>
              <div className="font-mono text-sm text-cyan-100">
                {Math.round(((failoverReport?.score ?? failoverReports[0]?.score) || 0) * 100)}%
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Reports</div>
              <div className="font-mono text-sm text-cyan-100">{failoverReports.length}</div>
            </div>
          </div>

          {failoverReport?.checks && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {failoverReport.checks.slice(0, 4).map((check) => (
                <div key={check.key} className="border border-cyan-900/25 bg-black/20 p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40">{check.label}</span>
                    <span className={`font-mono text-[8px] uppercase ${
                      check.status === 'pass' ? 'text-green-300' :
                      check.status === 'fail' ? 'text-red-300' :
                      'text-amber-300'
                    }`}>{check.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {failoverStatus && (
            <div className={`mt-3 flex items-start gap-2 p-3 border ${
              failoverStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
            }`} data-testid="failover-drill-status">
              {failoverStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
              <span className="font-mono text-[10px]">{failoverStatus.message}</span>
            </div>
          )}
        </div>

        <div className="mt-4 border border-cyan-900/35 bg-slate-950/30 p-3">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/45 flex items-center gap-2">
              <DatabaseBackup size={12} /> Release Evidence
            </div>
            <button
              onClick={createReleaseEvidence}
              disabled={releaseBusy}
              className="flex items-center gap-2 px-3 py-1.5 border border-cyan-500/40 text-cyan-300 font-display text-[9px] tracking-wider uppercase hover:bg-cyan-950/30 disabled:opacity-40"
              data-testid="release-evidence-run"
            >
              {releaseBusy ? <RefreshCw size={11} className="animate-spin" /> : <DatabaseBackup size={11} />}
              Bundle
            </button>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Status</div>
              <div className={`font-mono text-sm ${
                releaseBundle?.release_status === 'ready' ? 'text-green-400' :
                releaseBundle?.release_status === 'blocked' ? 'text-red-300' :
                'text-amber-300'
              }`}>
                {releaseBundle?.release_status || releaseBundles[0]?.release_status || 'Not Run'}
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Score</div>
              <div className="font-mono text-sm text-cyan-100">
                {Math.round(((releaseBundle?.score ?? releaseBundles[0]?.score) || 0) * 100)}%
              </div>
            </div>
            <div>
              <div className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40 mb-1">Bundles</div>
              <div className="font-mono text-sm text-cyan-100">{releaseBundles.length}</div>
            </div>
          </div>

          {releaseBundle?.items && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {releaseBundle.items.map((item) => (
                <div key={item.key} className="border border-cyan-900/25 bg-black/20 p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-[8px] tracking-widest uppercase text-cyan-300/40">{item.label}</span>
                    <span className={`font-mono text-[8px] uppercase ${
                      item.status === 'pass' ? 'text-green-300' :
                      item.status === 'fail' || item.status === 'missing' ? 'text-red-300' :
                      'text-amber-300'
                    }`}>{item.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {releaseStatus && (
            <div className={`mt-3 flex items-start gap-2 p-3 border ${
              releaseStatus.success ? 'border-green-500/30 bg-green-950/20 text-green-300' : 'border-red-500/30 bg-red-950/20 text-red-300'
            }`} data-testid="release-evidence-status">
              {releaseStatus.success ? <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" /> : <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
              <span className="font-mono text-[10px]">{releaseStatus.message}</span>
            </div>
          )}
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
