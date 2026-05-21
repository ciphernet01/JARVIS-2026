import React, { useState, useEffect } from 'react';
import LoginScreen from './components/LoginScreen';
import Dashboard from './components/Dashboard';
import BootSequence from './components/BootSequence';
import OnboardingScreen from './components/OnboardingScreen';
import NeuralTutorial from './components/NeuralTutorial';

const API = process.env.REACT_APP_BACKEND_URL || '';

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [booted, setBooted] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [tutorialComplete, setTutorialComplete] = useState(false);
  const [initialPanel, setInitialPanel] = useState('control');
  const [preferences, setPreferences] = useState(null);

  const applyPreferences = (prefs) => {
    if (!prefs) return;
    document.documentElement.lang = (prefs.language || 'en-US').split('-')[0];
    document.body.dataset.jarvisLanguage = prefs.language || 'en-US';
    document.body.classList.toggle('jarvis-high-contrast', Boolean(prefs.high_contrast));
    document.body.classList.toggle('jarvis-reduced-motion', Boolean(prefs.reduced_motion));
    document.body.classList.toggle('jarvis-large-text', Boolean(prefs.large_text));
    document.body.classList.toggle('jarvis-scanlines-off', prefs.scanlines === false);
  };

  useEffect(() => {
    const saved = localStorage.getItem('jarvis_token');
    setOnboardingComplete(localStorage.getItem('jarvis_onboarding_complete') === 'true');
    setTutorialComplete(localStorage.getItem('jarvis_tutorial_complete') === 'true');
    if (saved) {
      setToken(saved);
      setAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const loadPreferences = async () => {
      try {
        const resp = await fetch(`${API}/api/os/preferences`, {
          headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (cancelled) return;
        setPreferences(data.preferences);
        applyPreferences(data.preferences);
      } catch {
        // Preferences are non-critical during boot; Settings can retry visibly.
      }
    };
    loadPreferences();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleLogin = (newToken) => {
    localStorage.setItem('jarvis_token', newToken);
    setToken(newToken);
    setAuthenticated(true);
    setOnboardingComplete(localStorage.getItem('jarvis_onboarding_complete') === 'true');
  };

  const handleLogout = () => {
    localStorage.removeItem('jarvis_token');
    setToken(null);
    setAuthenticated(false);
  };

  if (!booted) {
    return <BootSequence onComplete={() => setBooted(true)} />;
  }

  if (!authenticated) {
    return <LoginScreen onLogin={handleLogin} api={API} />;
  }

  if (!onboardingComplete) {
    return (
      <OnboardingScreen
        api={API}
        token={token}
        onUnauthorized={handleLogout}
        onComplete={() => setOnboardingComplete(true)}
        onOpenSettings={() => {
          localStorage.setItem('jarvis_onboarding_complete', 'true');
          setInitialPanel('settings');
          setOnboardingComplete(true);
        }}
      />
    );
  }

  return (
    <>
      {!tutorialComplete && <NeuralTutorial onComplete={() => {
        setTutorialComplete(true);
        localStorage.setItem('jarvis_tutorial_complete', 'true');
      }} />}
      <Dashboard token={token} api={API} onLogout={handleLogout} initialPanel={initialPanel} preferences={preferences} onPreferencesChange={(prefs) => {
        setPreferences(prefs);
        applyPreferences(prefs);
      }} />
    </>
  );
}

export default App;
