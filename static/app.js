/* ══════════════════════════════════════════════════════════════════════════
   JARVIS HUD Dashboard — Application Logic
   ══════════════════════════════════════════════════════════════════════════ */

const API = '';  // Same origin

// ── Security & Global Fetch Override ────────────────────────────────────────
(function() {
  const originalFetch = window.fetch;
  window.fetch = async (...args) => {
    let [resource, config] = args;
    const token = localStorage.getItem('jarvis_token');
    
    // Only inject token for local JARVIS API calls
    if (token && (typeof resource === 'string' && (resource.startsWith('/api') || resource.startsWith(API + '/api')))) {
      if (!config) config = {};
      if (!config.headers) config.headers = {};
      
      // Handle both Headers object and plain object
      if (config.headers instanceof Headers) {
        config.headers.set('X-JARVIS-TOKEN', token);
      } else {
        config.headers['X-JARVIS-TOKEN'] = token;
      }
    }
    
    const response = await originalFetch(resource, config);
    
    // If we get a 401 Unauthorized, the session might have expired or server restarted
    if (response.status === 401 && !resource.includes('/api/verify_face')) {
      console.warn('Security session invalid. Redirecting to login.');
      localStorage.removeItem('jarvis_token');
      window.location.href = '/';
    }
    
    return response;
  };
})();

// ── State ───────────────────────────────────────────────────────────────────
let weatherCache = null;
let weatherLastFetched = 0;
const WEATHER_INTERVAL = 300_000; // 5 min
const SYSTEM_INTERVAL = 3_000;    // 3s
let recognition = null;
let listening = false;
let speechEnabled = true;
let handsFreeMode = false;
let autoRestartListening = false;
let awaitingVoiceCommand = false;
const WAKE_WORDS = ['jarvis', 'hey jarvis', 'okay jarvis'];
let lastJarvisResponse = '';

function showPredictiveIndicator() {
  const terminal = $('.terminal-container');
  if (terminal) {
    terminal.classList.add('predictive-pulse');
    setTimeout(() => terminal.classList.remove('predictive-pulse'), 2000);
  }
}

// ── DOM References ──────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Initialise ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  updateCalendar();
  setInterval(updateClock, 1000);

  initVoiceControls();
  initWorldMap();

  fetchSystemMetrics();
  setInterval(fetchSystemMetrics, SYSTEM_INTERVAL);

  fetchWeather();
  setInterval(() => fetchWeather(), WEATHER_INTERVAL);

  fetchStatus();
  setInterval(fetchStatus, 10_000);

  fetchHistory();
  
  initOpticalSensor();

  // Terminal input
  const input = $('#cmd-input');
  const sendBtn = $('#cmd-send');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCommand();
  });
  sendBtn.addEventListener('click', sendCommand);

  const voiceToggle = $('#voice-toggle');
  if (voiceToggle) {
    voiceToggle.addEventListener('click', toggleVoiceRecognition);
  }

  const speakToggle = $('#speak-toggle');
  if (speakToggle) {
    speakToggle.addEventListener('click', toggleSpeechOutput);
  }

  const handsFreeToggle = $('#handsfree-toggle');
  if (handsFreeToggle) {
    handsFreeToggle.addEventListener('click', toggleHandsFreeMode);
  }

  // Quick action buttons
  $$('.quick-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const cmd = btn.dataset.cmd;
      if (cmd) {
        input.value = cmd;
        sendCommand();
      }
    });
  });

  // Dock buttons
  setupDock();

  // Terminal feedback
  appendTerminalMsg('system', 'JARVIS Neural Interface Online. All systems nominal.');
  appendTerminalMsg('system', 'HUD Dashboard initialized. Awaiting commands...');
  
  // Autonomous Proactive Briefing (One-time per login)
  if (!sessionStorage.getItem('briefing_played')) {
    setTimeout(runAutonomousBriefing, 2000); // Wait for animations to settle
  }
});

async function runAutonomousBriefing() {
  try {
    appendTerminalMsg('system', 'Initiating autonomous briefing sequence...');
    const resp = await fetch('/api/briefing');
    if (!resp.ok) return;
    const data = await resp.json();
    
    if (data.summary) {
      appendTerminalMsg('jarvis', data.summary);
      speakText(data.summary);
      sessionStorage.setItem('briefing_played', 'true');
    }
  } catch (e) {
    console.error('Autonomous briefing failed:', e);
  }
}

// ── Voice Controls ─────────────────────────────────────────────────────────
function initVoiceControls() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceStatus = $('#voice-status');

  if (!SpeechRecognition) {
    if (voiceStatus) voiceStatus.textContent = 'Voice not supported in this browser';
    const voiceToggle = $('#voice-toggle');
    if (voiceToggle) voiceToggle.disabled = true;
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.continuous = true;

  recognition.onstart = () => {
    listening = true;
    updateVoiceStatus('Listening...');
    setVoiceButtonState(true);
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[event.results.length - 1][0].transcript.trim();
    const normalized = transcript.toLowerCase();
    const hasWakeWord = containsWakeWord(normalized);
    const cleaned = stripWakeWord(transcript);

    // In hands-free mode, only respond after a wake word or when already awaiting a command.
    if (handsFreeMode && !awaitingVoiceCommand && !hasWakeWord) {
      return;
    }

    if (handsFreeMode && hasWakeWord && !cleaned) {
      awaitingVoiceCommand = true;
      updateVoiceStatus('Wake word detected');
      appendTerminalMsg('system', 'Wake word heard. Ready for the next command.');
      await speakText('Yes?');
      return;
    }

    const commandText = cleaned || transcript;
    const input = $('#cmd-input');
    if (input) input.value = commandText;
    updateVoiceStatus('Processing command...');
    appendTerminalMsg('system', `Heard: ${commandText}`);

    // Stop listening while the assistant answers to avoid self-capture.
    awaitingVoiceCommand = false;
    if (recognition && listening) {
      autoRestartListening = false;
      try {
        recognition.stop();
      } catch {
        // ignore stop race
      }
    }

    await sendCommand({ source: 'voice' });
  };

  recognition.onerror = (event) => {
    appendTerminalMsg('error', `Voice error: ${event.error}`);
    updateVoiceStatus(`Voice error: ${event.error}`);
    awaitingVoiceCommand = false;
  };

  recognition.onend = () => {
    listening = false;
    updateVoiceStatus('Voice idle');
    setVoiceButtonState(false);
    if (autoRestartListening) {
      setTimeout(() => {
        try {
          recognition.start();
        } catch {
          // ignore restart races
        }
      }, 350);
    }
  };
}

function toggleVoiceRecognition() {
  if (!recognition) {
    appendTerminalMsg('error', 'Voice input is not supported in this browser.');
    return;
  }

  try {
    if (listening) recognition.stop();
    else {
      autoRestartListening = false;
      recognition.continuous = handsFreeMode;
      cancelSpeechOutput();
      recognition.start();
    }
  } catch (e) {
    appendTerminalMsg('error', `Voice start failed: ${e.message}`);
  }
}

function toggleHandsFreeMode() {
  handsFreeMode = !handsFreeMode;
  autoRestartListening = handsFreeMode;

  const btn = $('#handsfree-toggle');
  if (btn) {
    btn.textContent = handsFreeMode ? 'HANDS-FREE: ON' : 'HANDS-FREE: OFF';
    btn.classList.toggle('voice-btn--active', handsFreeMode);
  }

  if (recognition) recognition.continuous = handsFreeMode;

  updateVoiceStatus(handsFreeMode ? 'Hands-free mode ready' : 'Voice idle');
  appendTerminalMsg('system', `Hands-free mode ${handsFreeMode ? 'enabled' : 'disabled'}.`);

  if (handsFreeMode && !listening && recognition) {
    try {
      cancelSpeechOutput();
      recognition.start();
      autoRestartListening = true;
    } catch (e) {
      appendTerminalMsg('error', `Could not start hands-free listening: ${e.message}`);
    }
  }
}

function toggleSpeechOutput() {
  speechEnabled = !speechEnabled;
  const btn = $('#speak-toggle');
  if (btn) btn.textContent = speechEnabled ? 'SPEAK: ON' : 'SPEAK: OFF';
  if (!speechEnabled) window.speechSynthesis?.cancel();
  appendTerminalMsg('system', `Speech output ${speechEnabled ? 'enabled' : 'disabled'}.`);
}

function updateVoiceStatus(text) {
  const el = $('#voice-status');
  if (el) el.textContent = text;
}

function setVoiceButtonState(active) {
  const btn = $('#voice-toggle');
  if (!btn) return;
  btn.textContent = active ? 'STOP LISTENING' : 'VOICE';
  btn.classList.toggle('voice-btn--active', active);
}

let preferredVoice = null;

function loadPreferredVoice() {
  if (!window.speechSynthesis) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return;
  
  // Prefer British male voices to sound like JARVIS
  const preferredNames = [
    'Google UK English Male',
    'Microsoft George',
    'Daniel', // macOS
    'Google US English'
  ];
  
  for (const name of preferredNames) {
    const found = voices.find(v => v.name.includes(name));
    if (found) {
      preferredVoice = found;
      return;
    }
  }
  // Fallback to first English voice
  preferredVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
}

// Load voices when they are ready
if (window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = loadPreferredVoice;
}

function stripMarkdown(text) {
  // Remove markdown symbols: asterisks, hashes, backticks, tildes, greater-thans.
  let cleaned = text.replace(/[*_#`~>]+/g, '');
  // Replace links [label](url) with just 'label'
  cleaned = cleaned.replace(/\[(.*?)\]\(.*?\)/g, '$1');
  return cleaned;
}

function speakText(text) {
  return new Promise((resolve) => {
    if (!speechEnabled || !window.speechSynthesis || !text) {
      resolve();
      return;
    }

    try {
      window.speechSynthesis.cancel();

      // Anti-loop protection: stop listening while speaking
      const wasListening = listening;
      if (wasListening && recognition) {
        recognition.stop();
        listening = false;
        if ($('#voice-status')) $('#voice-status').textContent = 'Jarvis is speaking...';
      }

      // Strip markdown so JARVIS doesn't pronounce "asterisk asterisk"
      const cleanText = stripMarkdown(text);
      const utterance = new SpeechSynthesisUtterance(cleanText);
      
      if (!preferredVoice) loadPreferredVoice();
      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }
      
      utterance.lang = 'en-GB';
      // Fine-tuned for dry British cynicism
      utterance.rate = 1.1; 
      utterance.pitch = 0.85; 
      utterance.volume = 1.0; // Maximize output gain

      const resumeListening = () => {
        if (wasListening && recognition) {
          try {
            recognition.start();
            listening = true;
            autoRestartListening = true;
          } catch (e) {
            console.warn('Voice restart failed:', e);
          }
        }
        resolve();
      };

      utterance.onend = resumeListening;
      utterance.onerror = resumeListening;
      
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis failed:', e);
      resolve();
    }
  });
}

function cancelSpeechOutput() {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

function stripWakeWord(text) {
  let cleaned = text.trim();
  for (const wake of WAKE_WORDS) {
    const escaped = escapeRegex(wake);
    const startRegex = new RegExp(`^${escaped}[,\\s]+`, 'i');
    const wordRegex = new RegExp(`\\b${escaped}\\b`, 'i');
    cleaned = cleaned.replace(startRegex, '');
    cleaned = cleaned.replace(wordRegex, '');
  }
  cleaned = cleaned.replace(/^[,\s]+|[,\s]+$/g, '').trim();
  return cleaned;
}

function containsWakeWord(text) {
  const normalized = text.toLowerCase();
  return WAKE_WORDS.some((wake) => normalized.includes(wake));
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ── Clock & Calendar ────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');

  const clockEl = $('#top-clock');
  if (clockEl) clockEl.textContent = `${h}:${m}:${s}`;

  const reactorTime = $('#reactor-time');
  if (reactorTime) reactorTime.textContent = `${h}:${m}`;

  // Top bar date
  const dateEl = $('#top-date');
  if (dateEl) {
    const options = { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' };
    dateEl.textContent = now.toLocaleDateString('en-US', options).toUpperCase();
  }
}

function updateCalendar() {
  const now = new Date();
  const dayNum = $('#cal-day');
  const monthEl = $('#cal-month');
  const weekdayEl = $('#cal-weekday');
  const yearEl = $('#cal-year');

  if (dayNum) dayNum.textContent = now.getDate();
  if (monthEl) monthEl.textContent = now.toLocaleDateString('en-US', { month: 'long' }).toUpperCase();
  if (weekdayEl) weekdayEl.textContent = now.toLocaleDateString('en-US', { weekday: 'long' });
  if (yearEl) yearEl.textContent = now.getFullYear();

  // Week row
  const weekRow = $('#week-row');
  if (weekRow) {
    weekRow.innerHTML = '';
    const dayOfWeek = now.getDay();
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - dayOfWeek);

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      const el = document.createElement('div');
      el.className = 'week-row__day' + (d.getDate() === now.getDate() ? ' week-row__day--today' : '');
      el.textContent = d.getDate();
      weekRow.appendChild(el);
    }
  }
}

// ── System Metrics ──────────────────────────────────────────────────────────
async function fetchSystemMetrics() {
  try {
    const resp = await fetch(`${API}/api/system`);
    if (!resp.ok) return;
    const data = await resp.json();
    updateGauge('cpu', data.cpu.percent, `${data.cpu.cores} Cores · ${Math.round(data.cpu.freq)} MHz`);
    updateGauge('memory', data.memory.percent, `${data.memory.used_gb} / ${data.memory.total_gb} GB`);
    updateGauge('disk', data.disk.percent, `${data.disk.used_gb} / ${data.disk.total_gb} GB`);

    if (data.battery) {
      const battEl = document.getElementById('gauge-battery');
      if (battEl) {
        battEl.style.display = '';
        const plugged = data.battery.plugged ? ' ⚡' : '';
        updateGauge('battery', data.battery.percent, `${data.battery.percent}%${plugged}`);

        // Color coding
        const gauge = battEl.closest('.gauge');
        gauge.classList.remove('gauge--warning', 'gauge--danger');
        if (data.battery.percent < 20) gauge.classList.add('gauge--danger');
        else if (data.battery.percent < 40) gauge.classList.add('gauge--warning');
      }
    }

    // Network
    const netSent = $('#net-sent');
    const netRecv = $('#net-recv');
    if (netSent) netSent.textContent = formatBytes(data.network.bytes_sent);
    if (netRecv) netRecv.textContent = formatBytes(data.network.bytes_recv);
  } catch (e) {
    console.warn('System metrics fetch failed:', e);
  }
}

function updateGauge(id, percent, detail) {
  const circumference = 2 * Math.PI * 24;  // r=24
  const fill = $(`#gauge-${id}-fill`);
  const value = $(`#gauge-${id}-value`);
  const bar = $(`#gauge-${id}-bar`);
  const detailEl = $(`#gauge-${id}-detail`);

  if (fill) {
    const offset = circumference - (percent / 100) * circumference;
    fill.style.strokeDasharray = circumference;
    fill.style.strokeDashoffset = offset;
  }
  if (value) value.textContent = `${Math.round(percent)}%`;
  if (bar) bar.style.width = `${percent}%`;
  if (detailEl) detailEl.textContent = detail;
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

// ── Weather ─────────────────────────────────────────────────────────────────
async function fetchWeather() {
  try {
    const resp = await fetch(`${API}/api/weather`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.error) return;

    const tempEl = $('#weather-temp');
    const descEl = $('#weather-desc');
    const locEl = $('#weather-location');
    const humidEl = $('#weather-humid');
    const windEl = $('#weather-wind');
    const feelsEl = $('#weather-feels');
    const windDirEl = $('#weather-winddir');

    if (tempEl) tempEl.innerHTML = `${data.temp_c}<span>°C</span>`;
    if (descEl) descEl.textContent = data.description;
    if (locEl) locEl.textContent = `${data.location}, ${data.country}`;
    if (humidEl) humidEl.textContent = `${data.humidity}%`;
    if (windEl) windEl.textContent = `${data.wind_speed} km/h`;
    if (feelsEl) feelsEl.textContent = `${data.feels_like}°C`;
    if (windDirEl) windDirEl.textContent = data.wind_dir;
  } catch (e) {
    console.warn('Weather fetch failed:', e);
  }
}

// ── Status ──────────────────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const resp = await fetch(`${API}/api/status`);
    if (!resp.ok) return;
    const data = await resp.json();

    const skillsEl = $('#status-skills');
    const persEl = $('#status-persistence');
    const convsEl = $('#status-conversations');
    const platformEl = $('#status-platform');
    const uptimeEl = $('#status-uptime');

    if (skillsEl) skillsEl.textContent = data.skills_available;
    if (persEl) {
      persEl.textContent = data.persistence_enabled ? 'ONLINE' : 'OFFLINE';
      persEl.className = 'status-row__value ' + (data.persistence_enabled ? 'status-row__value--online' : 'status-row__value--offline');
    }
    if (convsEl) convsEl.textContent = data.conversation_count;
    if (platformEl) platformEl.textContent = data.platform;
    if (uptimeEl) {
      // Parse uptime string "H:MM:SS.ffffff" 
      const parts = data.uptime.split(':');
      if (parts.length >= 2) {
        const h = parseInt(parts[0]);
        const m = parseInt(parts[1]);
        const s = parseInt(parts[2]);
        uptimeEl.textContent = `${h}h ${m}m ${s}s`;
      }
    }
  } catch (e) {
    console.warn('Status fetch failed:', e);
  }
}

// ── Conversation History ────────────────────────────────────────────────────
async function fetchHistory() {
  try {
    const resp = await fetch(`${API}/api/history?limit=20`);
    if (!resp.ok) return;
    const data = await resp.json();
    const feedList = $('#activity-list');
    if (!feedList || !data.history) return;
    feedList.innerHTML = '';
    data.history.forEach((entry) => {
      const item = document.createElement('div');
      item.className = 'activity-item';
      const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';
      item.innerHTML = `
        <div class="activity-item__time">${time}</div>
        <div class="activity-item__text"><strong>${entry.role === 'user' ? 'YOU' : 'JARVIS'}:</strong> ${escapeHtml(entry.text)}</div>
      `;
      feedList.appendChild(item);
    });
    feedList.scrollTop = feedList.scrollHeight;
  } catch (e) {
    console.warn('History fetch failed:', e);
  }
}

// ── Command Submission ──────────────────────────────────────────────────────
async function sendCommand(options = {}) {
  const { source = 'manual' } = options;
  const input = $('#cmd-input');
  const command = input.value.trim();
  if (!command) return;
  input.value = '';

  cancelSpeechOutput();

  appendTerminalMsg('user', command);
  setProcessing(true);

  // If request takes longer than 2.5s, inform the user we are accessing the Neural Net
  const waitingTimeout = setTimeout(() => {
    appendTerminalMsg('system', 'Accessing Neural Net...');
    speakText('Accessing Neural Net, please wait...');
  }, 2500);

  try {
    const resp = await fetch(`${API}/api/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    const data = await resp.json();
    
    // Stop the accessing neural net message if it finished early
    clearTimeout(waitingTimeout);

    if (data.error) {
      appendTerminalMsg('error', data.error);
    } else {
      const jarvisResponse = data.response;
      
      // Predictive Analysis Trigger
      if (jarvisResponse.includes('sir?') || jarvisResponse.includes('took the liberty') || jarvisResponse.includes('anticipate')) {
        showPredictiveIndicator();
      }
      
      appendTerminalMsg('jarvis', jarvisResponse);
      lastJarvisResponse = jarvisResponse;
      await speakText(jarvisResponse);
    }
    // Refresh activity feed & status
    fetchHistory();
    fetchStatus();
  } catch (e) {
    clearTimeout(waitingTimeout);
    appendTerminalMsg('error', `Connection error: ${e.message}`);
  } finally {
    clearTimeout(waitingTimeout);
    setProcessing(false);
    if (source === 'voice' || handsFreeMode) {
      awaitingVoiceCommand = false;
      if (recognition && !listening) {
        autoRestartListening = handsFreeMode;
        if (handsFreeMode) {
          try {
            recognition.start();
          } catch {
            // ignore restart race
          }
        }
      }
    }
  }
}

function setProcessing(active) {
  const statusChip = $('#status-chip');
  if (!statusChip) return;
  if (active) {
    statusChip.textContent = 'PROCESSING';
    statusChip.classList.remove('status-indicator--online');
    statusChip.classList.add('status-indicator--processing');
    statusChip.style.color = '#ffc107';
    statusChip.style.borderColor = 'rgba(255, 193, 7, 0.3)';
    statusChip.style.background = 'rgba(255, 193, 7, 0.06)';
  } else {
    statusChip.textContent = 'ONLINE';
    statusChip.classList.remove('status-indicator--processing');
    statusChip.classList.add('status-indicator--online');
    statusChip.style.color = '';
    statusChip.style.borderColor = '';
    statusChip.style.background = '';
  }
}

// ── Terminal Output ─────────────────────────────────────────────────────────
function appendTerminalMsg(type, text) {
  const output = $('#terminal-output');
  if (!output) return;
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

  const msg = document.createElement('div');
  msg.className = `msg msg--${type}`;
  msg.innerHTML = `<span class="msg__time">[${time}]</span> ${escapeHtml(text)}`;
  output.appendChild(msg);
  output.scrollTop = output.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Dock ────────────────────────────────────────────────────────────────────
function setupDock() {
  $$('.dock-btn[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      switch (action) {
        case 'youtube':
          window.open('https://youtube.com', '_blank');
          break;
        case 'google':
          window.open('https://google.com', '_blank');
          break;
        case 'github':
          window.open('https://github.com', '_blank');
          break;
        case 'stackoverflow':
          window.open('https://stackoverflow.com', '_blank');
          break;
        case 'instagram':
          window.open('https://instagram.com', '_blank');
          break;
        case 'music':
          $('#cmd-input').value = 'play music';
          sendCommand();
          break;
        case 'camera':
          $('#cmd-input').value = 'open camera';
          sendCommand();
          break;
        case 'email':
          $('#cmd-input').value = 'email';
          sendCommand();
          break;
        case 'settings':
          appendTerminalMsg('system', 'Settings panel coming soon...');
          break;
        case 'power':
          if (confirm('Are you sure you want to shutdown?')) {
            $('#cmd-input').value = 'shut down';
            sendCommand();
          }
          break;
      }
    });
  });
}

// ── Optical Sensor (Vision AI) ──────────────────────────────────────────────
async function initOpticalSensor() {
  const video = $('#vision-feed');
  const canvas = $('#vision-canvas');
  const frameStatus = $('#frame-sync-status');
  
  if (!video || !canvas) return;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ 
      video: { width: 640, height: 360, frameRate: 15 } 
    });
    video.srcObject = stream;
    
    // Start streaming frames to backend for situational awareness
    setInterval(() => streamOpticalFrames(video, canvas, frameStatus), 2000);
    appendTerminalMsg('system', 'Neural Optical Link established. Sensors active.');
  } catch (e) {
    console.warn('Optical sensor failed:', e);
    appendTerminalMsg('error', 'Optical sensors offline: ' + e.message);
  }
}

async function streamOpticalFrames(video, canvas, statusEl) {
  if (video.paused || video.ended) return;

  const ctx = canvas.getContext('2d');
  canvas.width = 320; // Downscale for bandwidth
  canvas.height = 180;
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  
  const frame = canvas.toDataURL('image/jpeg', 0.6);
  
  try {
      const start = performance.now();
      const resp = await fetch('/api/vision/frame', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ frame })
      });
      const end = performance.now();
      
      if (resp.ok && statusEl) {
          const fps = Math.round(1000 / (end - start + 2000));
          statusEl.textContent = `${fps} FPS / SYNC`;
          statusEl.classList.add('sensor-value--online');
      }
  } catch (e) {
      if (statusEl) statusEl.textContent = 'OFFLINE';
  }
}

 
 f u n c t i o n   i n i t W o r l d M a p ( )   { 
     i f   ( t y p e o f   d 3   = = =   ' u n d e f i n e d ' )   r e t u r n ; 
     c o n s t   c o n t a i n e r   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' w o r l d - m a p - c o n t a i n e r ' ) ; 
     i f   ( ! c o n t a i n e r )   r e t u r n ; 
 
     c o n s t   w i d t h   =   8 0 0 ; 
     c o n s t   h e i g h t   =   4 0 0 ; 
     c o n s t   s v g   =   d 3 . s e l e c t ( c o n t a i n e r ) . a p p e n d ( ' s v g ' ) 
         . a t t r ( ' v i e w B o x ' ,   \     0   \   \ \ ) 
         . s t y l e ( ' w i d t h ' ,   ' 1 0 0 % ' ) 
         . s t y l e ( ' h e i g h t ' ,   ' 1 0 0 % ' ) ; 
 
     c o n s t   p r o j e c t i o n   =   d 3 . g e o E q u i r e c t a n g u l a r ( ) 
         . s c a l e ( 1 2 0 ) 
         . t r a n s l a t e ( [ w i d t h   /   2 ,   h e i g h t   /   2 ] ) ; 
     c o n s t   p a t h   =   d 3 . g e o P a t h ( ) . p r o j e c t i o n ( p r o j e c t i o n ) ; 
 
     d 3 . j s o n ( ' h t t p s : / / r a w . g i t h u b u s e r c o n t e n t . c o m / h o l t z y / D 3 - g e o m a p / m a s t e r / m a g i c / w o r l d . g e o j s o n ' ) . t h e n ( d a t a   = >   { 
         s v g . a p p e n d ( ' g ' ) 
             . s e l e c t A l l ( ' p a t h ' ) 
             . d a t a ( d a t a . f e a t u r e s ) 
             . e n t e r ( ) . a p p e n d ( ' p a t h ' ) 
             . a t t r ( ' d ' ,   p a t h ) 
             . a t t r ( ' f i l l ' ,   ' n o n e ' ) 
             . a t t r ( ' s t r o k e ' ,   ' # 0 0 d 4 f f ' ) 
             . a t t r ( ' s t r o k e - w i d t h ' ,   0 . 5 ) 
             . a t t r ( ' o p a c i t y ' ,   0 . 8 ) ; 
 
         / /   A d d   s c a n n i n g   l i n e   o v e r   t h e   m a p 
         s v g . a p p e n d ( ' l i n e ' ) 
             . a t t r ( ' x 1 ' ,   0 ) . a t t r ( ' y 1 ' ,   0 ) 
             . a t t r ( ' x 2 ' ,   w i d t h ) . a t t r ( ' y 2 ' ,   0 ) 
             . a t t r ( ' s t r o k e ' ,   ' # 0 0 d 4 f f ' ) 
             . a t t r ( ' s t r o k e - w i d t h ' ,   2 ) 
             . a t t r ( ' o p a c i t y ' ,   0 . 5 ) 
             . a p p e n d ( ' a n i m a t e ' ) 
                 . a t t r ( ' a t t r i b u t e N a m e ' ,   ' y 1 ' ) 
                 . a t t r ( ' v a l u e s ' ,   \   ; \ ; 0 \ ) 
                 . a t t r ( ' d u r ' ,   ' 1 0 s ' ) 
                 . a t t r ( ' r e p e a t C o u n t ' ,   ' i n d e f i n i t e ' ) ; 
 
         s v g . a p p e n d ( ' l i n e ' ) 
             . a t t r ( ' x 1 ' ,   0 ) . a t t r ( ' y 1 ' ,   0 ) 
             . a t t r ( ' x 2 ' ,   w i d t h ) . a t t r ( ' y 2 ' ,   0 ) 
             . a t t r ( ' s t r o k e ' ,   ' # 0 0 d 4 f f ' ) 
             . a t t r ( ' s t r o k e - w i d t h ' ,   2 ) 
             . a t t r ( ' o p a c i t y ' ,   0 . 5 ) 
             . a p p e n d ( ' a n i m a t e ' ) 
                 . a t t r ( ' a t t r i b u t e N a m e ' ,   ' y 2 ' ) 
                 . a t t r ( ' v a l u e s ' ,   \   ; \ ; 0 \ ) 
                 . a t t r ( ' d u r ' ,   ' 1 0 s ' ) 
                 . a t t r ( ' r e p e a t C o u n t ' ,   ' i n d e f i n i t e ' ) ; 
     } ) . c a t c h ( e r r   = >   c o n s o l e . e r r o r ( ' M a p   l o a d   e r r o r ' ,   e r r ) ) ; 
 } 
  
 