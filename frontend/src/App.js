import React, { useState, useEffect } from 'react';
import LoginScreen from './components/LoginScreen';
import Dashboard from './components/Dashboard';

const API = process.env.REACT_APP_BACKEND_URL || '';

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem('jarvis_token');
    if (saved) {
      setToken(saved);
      setAuthenticated(true);
    }
  }, []);

  const handleLogin = (newToken) => {
    localStorage.setItem('jarvis_token', newToken);
    setToken(newToken);
    setAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('jarvis_token');
    setToken(null);
    setAuthenticated(false);
  };

  if (!authenticated) {
    return <LoginScreen onLogin={handleLogin} api={API} />;
  }

  return <Dashboard token={token} api={API} onLogout={handleLogout} />;
}

export default App;
