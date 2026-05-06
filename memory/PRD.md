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
- [x] Arc Reactor SVG animation
- [x] System diagnostics with live metrics
- [x] AI chat terminal (Gemini 2.5 Flash)
- [x] Developer Mode for coding assistance
- [x] Weather widget (real data from wttr.in)
- [x] Calendar widget
- [x] Voice I/O controls (Web Speech API)
- [x] System status panel
- [x] Bottom navigation dock
- [x] Session-based auth with token

## Testing Status
- Backend: 100% (17/17 tests passed)
- Frontend: 100% (all flows working)

## Prioritized Backlog

### P0 (Critical)
- None remaining

### P1 (High)
- VSCode extension integration for real IDE connectivity
- Ollama local model fallback (when no internet)
- Real face recognition via webcam
- Conversation history persistence view

### P2 (Medium)
- Multi-turn conversation context (chat memory across sessions)
- File management skills (read/write workspace files)
- Code execution sandbox
- Agent workflow planner UI
- Dark/light theme toggle
- Responsive mobile layout

### P3 (Low/Future)
- Email integration
- Calendar events from Google Calendar
- Spotify/music integration
- Smart home controls
- GitHub integration (PR reviews, commits)
- Screen capture & analysis

## Next Tasks
1. Add VSCode extension manifest for real IDE integration
2. Implement conversation history panel in UI
3. Add Ollama fallback when Gemini is unavailable
4. Implement real webcam face verification on login
