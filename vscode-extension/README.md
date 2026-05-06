# JARVIS AI Assistant - VS Code Extension

Your personal JARVIS AI coding assistant, directly in VS Code. Like having Tony Stark's AI writing code alongside you.

## Features

- **Code Completion** (`Ctrl+Shift+Space`) - Intelligent code completion at cursor
- **Explain Code** (`Ctrl+Shift+E`) - Select code and get a detailed explanation
- **Fix Bugs** (`Ctrl+Shift+F`) - Select buggy code for instant fixes
- **Refactor** - Select code for clean refactoring suggestions
- **Generate Code** - Describe what you need, JARVIS builds it
- **Chat Sidebar** - Ask JARVIS anything from the sidebar panel
- **Inline Completions** - Ghost text suggestions as you type (Copilot-style)

## Setup

### 1. Start the JARVIS Backend

```bash
cd /app/backend
uvicorn server:app --host 0.0.0.0 --port 8001
```

### 2. Configure the Extension

Open VS Code Settings (`Ctrl+,`) and set:

- `jarvis.serverUrl`: Your JARVIS backend URL (default: `http://localhost:8001`)
- `jarvis.authToken`: Will be auto-generated on first use
- `jarvis.autoComplete`: Enable/disable inline completions

### 3. Install the Extension

```bash
cd vscode-extension
npm install
npm run compile
# Then press F5 in VS Code to run in debug mode
# Or package with: npx vsce package
```

## Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `JARVIS: Chat` | `Ctrl+Shift+J` | Open chat input |
| `JARVIS: Explain` | `Ctrl+Shift+E` | Explain selected code |
| `JARVIS: Fix Bugs` | `Ctrl+Shift+F` | Fix selected code |
| `JARVIS: Refactor` | - | Refactor selected code |
| `JARVIS: Generate` | - | Generate code from description |
| `JARVIS: Complete` | `Ctrl+Shift+Space` | Complete at cursor |

## API Endpoints

The extension communicates with the JARVIS backend via:

- `POST /api/vscode/action` - All code actions
- `GET /api/vscode/status` - Connection status check
- `POST /api/auth/login` - Auto-authentication

## Architecture

```
VS Code Extension
    ├── Commands (chat, explain, fix, refactor, generate, complete)
    ├── Inline Completion Provider (ghost text as you type)
    ├── Sidebar Webview (chat panel)
    └── JARVIS API Client
            └── Backend (FastAPI + Gemini 2.5 Flash)
```

## Powered By

- **Gemini 2.5 Flash** - Primary AI model
- **JARVIS Backend** - FastAPI server with session auth
- **VS Code Extension API** - Native integration

---
*"I am JARVIS. I am always ready to assist you, Sir."*
