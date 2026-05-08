# JARVIS Neural Interface - PRD

## Original Problem Statement
User had an existing Python JARVIS AI assistant project (Flask-based, static HTML/JS/CSS frontend) with modules for LLM (Gemini + Ollama), voice, vision, skills, security, persistence, and agent workflows. They wanted:
1. Code review and optimization
2. UI/UX redesign to look like the real JARVIS from Iron Man/Avengers movies
3. Developer workspace that can build apps like Copilot/Cursor/Emergent
4. Gemini and Ollama integrations

## Architecture
- **Backend**: FastAPI (Python) on port 8001
  - Gemini 2.5 Flash via emergentintegrations library (Emergent LLM Key)
  - MongoDB for persistence (conversations, code sessions)
  - System metrics, weather, auth endpoints
- **Frontend**: React on port 3000
  - JARVIS HUD-style interface with Tailwind CSS
  - Framer Motion animations
  - Web Speech API for voice I/O
  - JetBrains Mono + Azeret Mono typography
- **Database**: MongoDB (local)

Only the React `3000` + FastAPI `8001` web stack is active. The older Flask/static dashboard is legacy and should not be used for new work.

## User Personas
- **Primary**: Developer/power user ("Sir") who wants an AI coding assistant with Iron Man aesthetics

## Core Requirements (Static)
- Biometric-style login screen
- Arc Reactor visualization (spinning SVG rings)
- System diagnostics (CPU/RAM/Disk gauges)
- AI Command Terminal (chat with Gemini)
- Developer Mode (coding assistance)
- Weather widget (wttr.in API)
- Calendar widget
- Voice input/output (Web Speech API)
- System status panel
- Bottom navigation dock

## What's Been Implemented (May 6, 2026)
- [x] Full FastAPI backend with Gemini AI integration
- [x] React frontend with JARVIS HUD design
- [x] Biometric login flow (simulated)
- [x] **Real webcam face verification** - Live camera feed on login, OpenCV Haar cascade face detection, face enrollment/comparison via histogram
- [x] Arc Reactor SVG animation
- [x] System diagnostics with live metrics
- [x] AI chat terminal (Gemini 2.5 Flash)
- [x] Developer Mode for coding assistance
- [x] **VSCode Extension API** - Full IDE integration with complete/explain/fix/refactor/generate/chat actions
- [x] **VSCode Extension Package** - Ready-to-install extension at /app/vscode-extension/
- [x] **Face Enrollment UI** - Settings panel with live camera, capture & enroll button, stored in MongoDB
- [x] Weather widget (real data from wttr.in)
- [x] Calendar widget
- [x] Voice I/O controls (Web Speech API)
- [x] System status panel
- [x] Bottom navigation dock
- [x] Session-based auth with token
- [x] Face enrollment endpoint for storing biometric profiles

## Testing Status
- Backend: 100% (36/36 tests passed)
- Frontend: 100% (all flows working)

## Prioritized Backlog

### P0 (Critical)
- None remaining

### P1 (High)
- Ollama local model fallback (when no internet)
- Real-time inline code completion streaming
- Conversation history persistence view in dashboard

### P2 (Medium)
- Multi-turn conversation context (chat memory across sessions)
- Face enrollment UI in dashboard settings
- Code execution sandbox in developer workspace
- Agent workflow planner UI
- Responsive mobile layout

### P3 (Low/Future)
- Email integration
- Calendar events from Google Calendar
- Spotify/music integration  
- Smart home controls
- GitHub integration (PR reviews, commits)
- Screen capture & analysis
- Voice-activated wake word ("Hey JARVIS")

## Next Tasks
1. Add Ollama fallback when Gemini is unavailable
2. Add face enrollment UI in the dashboard (Settings panel)
3. Implement conversation history panel
4. Add code execution sandbox
