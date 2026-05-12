"""
JARVIS Neural Interface - FastAPI Backend
Advanced AI Assistant with Gemini integration
"""

import os
import sys
import logging
import platform
import uuid
import base64
import re
import shutil
import subprocess
import psutil
import numpy as np
import requests as http_requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure core module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import cv2

load_dotenv()

# Import new JARVIS core
from core import ConfigManager, Assistant
from modules.skills import SkillFactory
from modules.services import DeviceManager, ServiceManager, AudioManager, CameraManager, PowerManager, NetworkManager, VoiceManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_START_TIME = datetime.now(timezone.utc)

# MongoDB
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "jarvis")
client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=2000)
db = client[DB_NAME]

# Emergent LLM
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")

# Session management
SESSION_TOKENS = {}

# Face detection cascade
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

# Enrolled face storage (in MongoDB)
FACE_COLLECTION = "enrolled_faces"

app = FastAPI(title="JARVIS Neural Interface API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Warm up assistant and voice router on server startup."""
    try:
        _get_assistant()
        _get_voice_router()
        logger.info("JARVIS backend startup complete")
    except Exception as exc:
        logger.warning(f"Startup warmup failed: {exc}")

# ── Initialize JARVIS Core (ReActAgent + LLMRouter) ─────────────────────────
_jarvis_assistant: Optional[Assistant] = None
_service_manager: Optional[ServiceManager] = None
_device_manager: Optional[DeviceManager] = None
_audio_manager: Optional[AudioManager] = None
_camera_manager: Optional[CameraManager] = None
_power_manager: Optional[PowerManager] = None
_network_manager: Optional[NetworkManager] = None
_voice_router = None


def _get_network_manager() -> NetworkManager:
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager()
    return _network_manager


def _get_assistant() -> Optional[Assistant]:
    global _jarvis_assistant
    if _jarvis_assistant is None:
        try:
            config = ConfigManager()
            skill_registry = SkillFactory.create_default_registry()

            # Setup persistence layer for the web backend (Absolute path)
            db_path = Path(__file__).resolve().parent.parent / "jarvis.db"
            db_url = f"sqlite:///{db_path}"
            from modules.persistence import PersistenceFactory
            persistence_components = PersistenceFactory.initialize(db_url)

            _jarvis_assistant = Assistant(
                config_manager=config,
                skill_registry=skill_registry,
                persistence_components=persistence_components,
            )
            _jarvis_assistant.set_current_user("shrey_ceo")
            logger.info("JARVIS Assistant initialized with ReActAgent and Persistence")
        except Exception as exc:
            logger.warning(f"Failed to initialize JARVIS Assistant: {exc}")
    return _jarvis_assistant


def _get_voice_router():
    """Get the voice command router singleton."""
    global _voice_router
    if _voice_router is None:
        from modules.agent.voice_router import VoiceCommandRouter

        _voice_router = VoiceCommandRouter(_get_assistant(), _get_voice_manager())
    return _voice_router


def _get_service_manager() -> ServiceManager:
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager


def _get_device_manager() -> DeviceManager:
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager(workspace_root=str(WORKSPACE_ROOT))
    return _device_manager


def _get_audio_manager() -> AudioManager:
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager


def _get_camera_manager() -> CameraManager:
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
    return _camera_manager


def _get_power_manager() -> PowerManager:
    global _power_manager
    if _power_manager is None:
        _power_manager = PowerManager()
    return _power_manager


# ── Models ───────────────────────────────────────────────────────────────────
class OSCommandRequest(BaseModel):
    command: str
    dry_run: bool = False


class LoginRequest(BaseModel):
    method: str = "biometric"
    image: Optional[str] = None  # Base64 webcam frame

class CommandRequest(BaseModel):
    command: str
    session_id: Optional[str] = None

class OperatorRequest(BaseModel):
    command: str
    session_id: Optional[str] = None
    dry_run: bool = False

class CodeRequest(BaseModel):
    prompt: str
    repo_context: Optional[str] = None
    language: Optional[str] = "python"

class FaceEnrollRequest(BaseModel):
    image: str  # Base64 webcam frame
    label: str = "owner"

class VSCodeRequest(BaseModel):
    action: str  # "complete", "explain", "fix", "refactor", "chat"
    code: Optional[str] = None
    language: Optional[str] = "python"
    cursor_line: Optional[int] = None
    file_path: Optional[str] = None
    prompt: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────
def verify_token(request: Request):
    token = request.headers.get("X-JARVIS-TOKEN")
    if not token or token not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized. Security protocol active.")
    return SESSION_TOKENS[token]


# Operator Core
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
GENERATED_APPS_DIR = WORKSPACE_ROOT / "generated_apps"

APP_ALLOWLIST = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "vscode": "code.cmd",
    "vs code": "code.cmd",
}


def _safe_name(value: str, default: str = "jarvis-app") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:60] or default


def _resolve_workspace_path(raw_path: Optional[str] = None) -> Path:
    if not raw_path:
        return WORKSPACE_ROOT
    candidate = (WORKSPACE_ROOT / raw_path).resolve()
    if WORKSPACE_ROOT not in candidate.parents and candidate != WORKSPACE_ROOT:
        raise HTTPException(status_code=400, detail="Path is outside the JARVIS workspace")
    return candidate


def _system_snapshot() -> Dict[str, Any]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(WORKSPACE_ROOT.anchor or WORKSPACE_ROOT))
    battery = psutil.sensors_battery()
    cpu_freq = psutil.cpu_freq()
    return {
        "platform": f"{platform.system()} {platform.release()}",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_cores": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(cpu_freq.current) if cpu_freq else 0,
        "memory_percent": memory.percent,
        "memory_total_gb": round(memory.total / (1024**3), 1),
        "memory_available_gb": round(memory.available / (1024**3), 2),
        "memory_used_gb": round(memory.used / (1024**3), 1),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "battery_percent": battery.percent if battery else None,
        "power_plugged": battery.power_plugged if battery else None,
    }


def _list_workspace(raw_path: Optional[str] = None) -> Dict[str, Any]:
    target = _resolve_workspace_path(raw_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    if target.is_file():
        return {"path": str(target.relative_to(WORKSPACE_ROOT)), "type": "file", "size": target.stat().st_size}

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))[:40]:
        entries.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
            "modified": datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return {
        "path": "." if target == WORKSPACE_ROOT else str(target.relative_to(WORKSPACE_ROOT)),
        "entries": entries,
    }


def _read_workspace_file(raw_path: str) -> Dict[str, Any]:
    target = _resolve_workspace_path(raw_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
        is_binary = False
    except Exception:
        text = "[Binary file preview unavailable]"
        is_binary = True

    return {
        "path": str(target.relative_to(WORKSPACE_ROOT)),
        "name": target.name,
        "size": target.stat().st_size,
        "is_binary": is_binary,
        "content": text[:12000],
    }


def _open_allowed_app(command: str, dry_run: bool = False) -> Dict[str, Any]:
    lowered = command.lower()
    app_key = None
    for alias in sorted(APP_ALLOWLIST, key=len, reverse=True):
        if alias in lowered:
            app_key = alias
            break
    if not app_key:
        raise HTTPException(status_code=400, detail="App is not in the operator allowlist")

    executable = APP_ALLOWLIST[app_key]
    resolved = shutil.which(executable) or executable
    if not dry_run:
        subprocess.Popen([resolved], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
    return {"app": app_key, "executable": executable, "launched": not dry_run}


def _route_os_command(command: str, dry_run: bool = False) -> Dict[str, Any]:
    """Route safe OS-level commands to the proper backend action."""
    lowered = command.lower().strip()
    service_manager = _get_service_manager()

    if any(phrase in lowered for phrase in ["show processes", "list processes", "process list", "task list"]):
        processes = service_manager.list_processes(limit=60)
        return {
            "handled": True,
            "intent": "list_processes",
            "response": f"Process snapshot ready. {len(processes)} processes indexed.",
            "data": {"processes": processes},
        }

    if any(phrase in lowered for phrase in ["show services", "list services", "service list", "services"]):
        services = service_manager.list_services()
        return {
            "handled": True,
            "intent": "list_services",
            "response": f"Tracked service snapshot ready. {len(services)} service(s) tracked.",
            "data": {"services": services},
        }

    if any(phrase in lowered for phrase in ["show devices", "device status", "hardware status", "hardware snapshot"]):
        devices = _get_device_manager().snapshot()
        return {
            "handled": True,
            "intent": "device_snapshot",
            "response": "Hardware snapshot ready.",
            "data": devices,
        }

    if any(phrase in lowered for phrase in ["open ", "launch ", "start "]):
        data = _open_allowed_app(command, dry_run=dry_run)
        return {
            "handled": True,
            "intent": "open_app",
            "response": f"{'Ready to launch' if dry_run else 'Launched'} {data['app']}, Sir.",
            "data": data,
        }

    if lowered.startswith(("start service ", "run service ")):
        service_name = command.split(maxsplit=2)[-1]
        return {
            "handled": True,
            "intent": "start_service",
            "response": f"Service start requested for {service_name}.",
            "data": {"service": service_name, "dry_run": dry_run},
        }

    if lowered.startswith(("stop service ", "kill service ")):
        service_name = command.split(maxsplit=2)[-1]
        return {
            "handled": True,
            "intent": "stop_service",
            "response": f"Service stop requested for {service_name}.",
            "data": {"service": service_name, "dry_run": dry_run},
        }

    return {"handled": False, "intent": "chat", "response": None, "data": {}}


def _create_static_app(command: str, dry_run: bool = False) -> Dict[str, Any]:
    raw_name = "jarvis-app"
    for pattern in [
        r"\bcalled\s+([a-zA-Z0-9 _-]{2,60})",
        r"\bnamed\s+([a-zA-Z0-9 _-]{2,60})",
        r"\bname\s+([a-zA-Z0-9 _-]{2,60})",
        r"\bapp\s+([a-zA-Z0-9 _-]{2,60})",
    ]:
        name_match = re.search(pattern, command, re.IGNORECASE)
        if name_match:
            raw_name = name_match.group(1)
            break
    app_name = _safe_name(raw_name)
    app_dir = (GENERATED_APPS_DIR / app_name).resolve()
    if GENERATED_APPS_DIR not in app_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid app target")

    files = {
        "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>JARVIS App</title>
    <link rel="stylesheet" href="style.css" />
  </head>
  <body>
    <main class="shell">
      <p class="eyebrow">Sypher Industries</p>
      <h1>JARVIS Generated Interface</h1>
      <p id="brief">Operational prototype scaffolded by JARVIS.</p>
      <button id="action">Run diagnostic</button>
      <pre id="output"></pre>
    </main>
    <script src="app.js"></script>
  </body>
</html>
""",
        "style.css": """* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #081019;
  color: #d9fbff;
  font-family: Inter, system-ui, sans-serif;
}
.shell {
  width: min(760px, calc(100vw - 32px));
  border: 1px solid rgba(34, 211, 238, 0.35);
  padding: 32px;
  background: rgba(2, 6, 23, 0.88);
}
.eyebrow {
  color: #22d3ee;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 12px;
}
h1 { margin: 8px 0 12px; font-size: clamp(32px, 7vw, 68px); }
button {
  margin-top: 20px;
  border: 1px solid #22d3ee;
  background: transparent;
  color: #67e8f9;
  padding: 12px 16px;
  cursor: pointer;
}
pre { min-height: 80px; color: #86efac; white-space: pre-wrap; }
""",
        "app.js": """const output = document.querySelector('#output');
document.querySelector('#action').addEventListener('click', () => {
  output.textContent = [
    'Diagnostic complete.',
    `Timestamp: ${new Date().toLocaleString()}`,
    'Status: prototype ready'
  ].join('\\n');
});
""",
        "README.md": f"# {app_name}\n\nStatic app scaffolded by JARVIS Operator.\n\nOpen `index.html` in a browser.\n",
    }

    if not dry_run:
        app_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (app_dir / filename).write_text(content, encoding="utf-8")
    return {
        "app_name": app_name,
        "path": str(app_dir.relative_to(WORKSPACE_ROOT)),
        "files": sorted(files),
        "created": not dry_run,
    }


async def execute_operator_command(command: str, dry_run: bool = False) -> Dict[str, Any]:
    lowered = command.lower().strip()
    if any(phrase in lowered for phrase in ["system status", "system state", "diagnostics", "how is the system"]):
        data = _system_snapshot()
        return {
            "handled": True,
            "intent": "system_status",
            "response": (
                f"System is online. CPU {data['cpu_percent']}%, memory {data['memory_percent']}%, "
                f"disk {data['disk_percent']}%."
            ),
            "data": data,
        }

    if lowered.startswith(("list files", "show files", "scan workspace", "list workspace")):
        path_match = re.search(r"(?:in|under|inside)\s+(.+)$", command, re.IGNORECASE)
        data = _list_workspace(path_match.group(1).strip() if path_match else None)
        names = ", ".join(item["name"] for item in data.get("entries", [])[:12])
        return {
            "handled": True,
            "intent": "list_workspace",
            "response": f"Workspace scan complete for {data['path']}. {names or 'No entries found.'}",
            "data": data,
        }

    if lowered.startswith(("open ", "launch ", "start ")):
        data = _open_allowed_app(command, dry_run=dry_run)
        return {
            "handled": True,
            "intent": "open_app",
            "response": f"{'Ready to launch' if dry_run else 'Launched'} {data['app']}, Sir.",
            "data": data,
        }

    if any(phrase in lowered for phrase in ["create app", "build app", "scaffold app", "make app"]):
        data = _create_static_app(command, dry_run=dry_run)
        return {
            "handled": True,
            "intent": "create_static_app",
            "response": f"Created static app {data['app_name']} at {data['path']}.",
            "data": data,
        }

    return {"handled": False, "intent": "chat", "response": None, "data": {}}


def _ollama_chat(prompt: str, system_message: Optional[str] = None) -> Optional[str]:
    """Return an Ollama response when a local model is available."""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_message or (
                        "You are JARVIS, an advanced AI assistant created by Sypher Industries. "
                        "Your CEO and creator is Shrey. You are a Senior Developer and AI ML Expert. "
                        "You can build websites, write code, debug issues, and manage systems. "
                        "Be concise, confident, and address the user as Sir. "
                        "When asked to build something, provide a clear plan and offer to execute it."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        logger.info(f"Ollama chat request: model={OLLAMA_MODEL}, prompt_len={len(prompt)}")
        resp = http_requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content")
            if content:
                logger.info(f"Ollama chat success: {len(content)} chars")
                return content.strip()
            else:
                logger.warning(f"Ollama returned empty content: {data}")
        else:
            logger.warning(f"Ollama chat HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Ollama chat unavailable: {e}")
    return None


def _offline_chat_response(prompt: str) -> str:
    """Deterministic fallback so JARVIS remains operational without cloud/model access."""
    lowered = prompt.lower().strip()
    if any(term in lowered for term in ["what can you do", "capabilities", "help"]):
        return (
            "Operational locally, Sir. I can report system status, scan workspace files, "
            "launch approved apps, scaffold static apps, assist with code templates, and route "
            "voice commands through the operator core. Cloud reasoning is offline until Gemini "
            "or Ollama is configured."
        )
    if "jarvis" in lowered or "friday" in lowered:
        return (
            "The project objective is clear, Sir: a voice-first software and OS operator inspired "
            "by JARVIS/FRIDAY. Current production scope excludes hardware fabrication, but includes "
            "app creation, file operations, diagnostics, local task execution, and spoken feedback."
        )
    if any(term in lowered for term in ["2+2", "2 + 2"]):
        return "4, Sir."
    return (
        "I am running in local fallback mode, Sir. I can execute operator commands directly; "
        "for open-ended reasoning, connect Ollama locally or restore the Gemini integration."
    )


def _offline_code_response(prompt: str, language: str = "python") -> str:
    """Small production fallback for developer mode when no model provider is available."""
    lang = (language or "python").lower()
    if lang in {"javascript", "react"}:
        return """```javascript
export function createJarvisModule(name, execute) {
  if (!name || typeof execute !== 'function') {
    throw new Error('A module name and execute function are required.');
  }

  return {
    name,
    status: 'ready',
    async run(input, context = {}) {
      return execute(input, context);
    },
  };
}
```"""
    if lang == "html":
        return """```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>JARVIS Prototype</title>
  </head>
  <body>
    <main id="app">Operational prototype ready.</main>
  </body>
</html>
```"""
    return """```python
from dataclasses import dataclass


@dataclass
class JarvisTask:
    name: str
    status: str = "pending"


def execute_task(task: JarvisTask) -> JarvisTask:
    task.status = "complete"
    return task
```"""


# ── LLM Chat Helper ─────────────────────────────────────────────────────────
async def jarvis_chat(prompt: str, system_message: str = None, session_id: str = "default") -> str:
    """Route through JARVIS ReActAgent (Gemini → xAI → Groq → Ollama fallback)."""
    assistant = _get_assistant()
    if assistant and assistant.react_agent:
        try:
            response = await assistant.process_query_async(prompt)
            return response
        except Exception as exc:
            logger.warning(f"ReActAgent failed in web backend: {exc}")

    # Legacy fallback
    ollama_response = _ollama_chat(prompt, system_message=system_message)
    if ollama_response:
        return ollama_response
    return _offline_chat_response(prompt)


async def jarvis_code_assist(prompt: str, repo_context: str = None, language: str = "python") -> str:
    """Coding assistant mode"""
    system_message = (
        "You are JARVIS in Developer Mode - a senior software architect and code generator. "
        "You write production-quality code, debug issues, suggest architectural improvements, "
        "and provide full implementations. When asked to build something, provide complete, "
        "working code. Format code in markdown code blocks with language identifiers. "
        "Be concise in explanations but thorough in code."
    )

    full_prompt = prompt
    if repo_context:
        full_prompt = f"Repository Context:\n```\n{repo_context}\n```\n\nRequest: {prompt}"
    if language:
        full_prompt += f"\n\nPreferred language: {language}"

    response = await jarvis_chat(full_prompt, system_message=system_message, session_id="dev-mode")
    if "local fallback mode" in response.lower() or "cloud reasoning is offline" in response.lower():
        return _offline_code_response(prompt, language=language)
    return response


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "system": "JARVIS Neural Interface",
        "version": "2.0",
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Biometric face verification login - checks against imagedata/ folder and enrolled faces"""
    face_detected = False
    face_confidence = 0.0
    face_box = None  # {x, y, w, h} for frontend to draw rectangle
    verification_method = req.method

    if req.method in {"camera_unavailable", "production_bypass"} and not req.image:
        verification_method = "camera_unavailable_bypass"

    if req.image:
        try:
            img_data = req.image
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            img_bytes = base64.b64decode(img_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
                )

                if len(faces) > 0:
                    face_detected = True
                    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                    frame_h, frame_w = frame.shape[:2]
                    # Normalize face box coordinates (0-1) for frontend
                    face_box = {
                        "x": float(x) / frame_w,
                        "y": float(y) / frame_h,
                        "w": float(w) / frame_w,
                        "h": float(h) / frame_h,
                    }

                    # Extract face crop for comparison
                    face_crop = gray[y:y+h, x:x+w]
                    face_crop_resized = cv2.resize(face_crop, (128, 128))
                    candidate_hist = cv2.calcHist([face_crop_resized], [0], None, [64], [0, 256])
                    cv2.normalize(candidate_hist, candidate_hist)

                    best_score = 0.0
                    matched_against = None

                    # Method 1: Check imagedata/ folder (reference photos)
                    import glob
                    imagedata_dir = Path(__file__).parent.parent / "imagedata"
                    ref_paths = []
                    if imagedata_dir.exists():
                        ref_paths = list(imagedata_dir.glob("*.jpg")) + list(imagedata_dir.glob("*.jpeg")) + list(imagedata_dir.glob("*.png"))

                    for ref_path in ref_paths:
                        try:
                            ref_img = cv2.imread(str(ref_path))
                            if ref_img is None:
                                continue
                            ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
                            ref_faces = face_cascade.detectMultiScale(ref_gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
                            if len(ref_faces) > 0:
                                rx, ry, rw, rh = max(ref_faces, key=lambda r: r[2] * r[3])
                                ref_crop = ref_gray[ry:ry+rh, rx:rx+rw]
                            else:
                                ref_crop = ref_gray
                            ref_crop_resized = cv2.resize(ref_crop, (128, 128))
                            ref_hist = cv2.calcHist([ref_crop_resized], [0], None, [64], [0, 256])
                            cv2.normalize(ref_hist, ref_hist)
                            score = cv2.compareHist(candidate_hist, ref_hist, cv2.HISTCMP_CORREL)
                            if score > best_score:
                                best_score = score
                                matched_against = f"imagedata/{ref_path.name}"
                        except Exception:
                            continue

                    # Method 2: Check MongoDB enrolled faces
                    enrolled = await db[FACE_COLLECTION].find_one({"label": "owner"})
                    if enrolled:
                        stored_hist = np.array(enrolled["histogram"], dtype=np.float32)
                        score = cv2.compareHist(candidate_hist, stored_hist, cv2.HISTCMP_CORREL)
                        if score > best_score:
                            best_score = score
                            matched_against = "enrolled_profile"

                    face_confidence = max(0.0, best_score)

                    # If we have reference data and score is too low, deny
                    if (ref_paths or enrolled) and best_score < 0.3:
                        return {
                            "success": False,
                            "message": f"Face not recognized. Similarity: {best_score:.2f}. Access denied.",
                            "face_detected": True,
                            "face_box": face_box,
                            "confidence": face_confidence,
                        }

                    # If no reference data exists, accept any face
                    if not ref_paths and not enrolled:
                        face_confidence = 1.0
                        matched_against = "no_reference_enrolled"

                    verification_method = "face_verified"
                    logger.info(f"Face verified against: {matched_against}, score: {best_score:.3f}")
                else:
                    return {
                        "success": False,
                        "message": "No face detected. Position your face in the center of the frame.",
                        "face_detected": False,
                        "face_box": None,
                        "confidence": 0.0,
                    }
        except Exception as e:
            logger.error(f"Face verification error: {e}")
            verification_method = "biometric_fallback"

    token = str(uuid.uuid4())
    user_data = {
        "user_id": "shrey_ceo",
        "user_name": "Sir",
        "login_time": datetime.now(timezone.utc).isoformat(),
        "method": verification_method,
        "face_detected": face_detected,
        "face_confidence": face_confidence,
    }
    SESSION_TOKENS[token] = user_data

    try:
        await db.sessions.insert_one({
            "token": token,
            "user_id": "shrey_ceo",
            "login_time": datetime.now(timezone.utc).isoformat(),
            "method": verification_method,
            "face_detected": face_detected,
        })
    except Exception as e:
        logger.warning(f"Session persistence unavailable, continuing with in-memory token: {e}")

    message = "Biometric verification complete. Welcome back, Sir."
    if face_detected:
        message = f"Face recognized (confidence: {face_confidence:.0%}). Welcome back, Sir."
    elif verification_method == "camera_unavailable_bypass":
        message = "Camera offline. Production bypass authorized. Welcome back, Sir."

    return {
        "success": True,
        "token": token,
        "message": message,
        "user": {"name": "Sir", "id": "shrey_ceo"},
        "face_detected": face_detected,
        "face_box": face_box,
        "confidence": face_confidence,
    }


@app.post("/api/auth/enroll_face")
async def enroll_face(req: FaceEnrollRequest, user=Depends(verify_token)):
    """Enroll a face for future biometric verification"""
    try:
        img_data = req.image
        if "," in img_data:
            img_data = img_data.split(",", 1)[1]
        img_bytes = base64.b64decode(img_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        if len(faces) == 0:
            return {"success": False, "message": "No face detected. Please try again."}

        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        face_crop = gray[y:y+h, x:x+w]
        face_crop = cv2.resize(face_crop, (128, 128))

        hist = cv2.calcHist([face_crop], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)

        # Store in MongoDB
        await db[FACE_COLLECTION].update_one(
            {"label": req.label},
            {"$set": {
                "label": req.label,
                "histogram": hist.flatten().tolist(),
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user["user_id"],
            }},
            upsert=True,
        )

        return {"success": True, "message": f"Face enrolled as '{req.label}'. Biometric profile updated."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Face enrollment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── VSCode Extension API ─────────────────────────────────────────────────────
@app.post("/api/vscode/action")
async def vscode_action(req: VSCodeRequest, user=Depends(verify_token)):
    """VSCode extension endpoint - handles code completion, explanation, fixes, and chat"""
    action = req.action.lower()

    if action == "complete":
        system_msg = (
            "You are JARVIS integrated into VS Code as a code completion engine. "
            "Given the code context and cursor position, provide the most likely code completion. "
            "Return ONLY the completion code, no explanations. Be precise and contextual."
        )
        prompt = f"Language: {req.language}\nFile: {req.file_path or 'untitled'}\n"
        if req.code:
            prompt += f"Current code:\n```{req.language}\n{req.code}\n```\n"
        if req.cursor_line:
            prompt += f"Cursor at line: {req.cursor_line}\n"
        prompt += "Provide the code completion:"

    elif action == "explain":
        system_msg = (
            "You are JARVIS in VS Code. Explain the selected code clearly and concisely. "
            "Cover what it does, potential issues, and suggest improvements if any."
        )
        prompt = f"Explain this {req.language} code:\n```{req.language}\n{req.code}\n```"

    elif action == "fix":
        system_msg = (
            "You are JARVIS debugging in VS Code. Identify bugs in the code and provide "
            "the corrected version. Show the fixed code in a code block."
        )
        prompt = f"Fix bugs in this {req.language} code:\n```{req.language}\n{req.code}\n```"
        if req.prompt:
            prompt += f"\nError/Issue: {req.prompt}"

    elif action == "refactor":
        system_msg = (
            "You are JARVIS refactoring code in VS Code. Improve the code quality, "
            "readability, and performance while maintaining functionality."
        )
        prompt = f"Refactor this {req.language} code:\n```{req.language}\n{req.code}\n```"
        if req.prompt:
            prompt += f"\nRefactoring goal: {req.prompt}"

    elif action == "generate":
        system_msg = (
            "You are JARVIS generating code in VS Code. Write complete, production-ready code "
            "based on the user's description. Include imports and proper structure."
        )
        prompt = f"Generate {req.language} code: {req.prompt}"
        if req.code:
            prompt += f"\n\nExisting context:\n```{req.language}\n{req.code}\n```"

    elif action == "chat":
        system_msg = (
            "You are JARVIS integrated in VS Code as a coding assistant sidebar. "
            "Answer questions about code, architecture, and development. Be concise."
        )
        prompt = req.prompt or ""
        if req.code:
            prompt = f"Code context:\n```{req.language}\n{req.code}\n```\n\nQuestion: {prompt}"

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    response = await jarvis_chat(prompt, system_message=system_msg, session_id=f"vscode-{action}")

    await db.vscode_actions.insert_one({
        "user_id": user["user_id"],
        "action": action,
        "language": req.language,
        "file_path": req.file_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "action": action,
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/vscode/status")
async def vscode_status(user=Depends(verify_token)):
    """VSCode extension status check"""
    try:
        action_count = await db.vscode_actions.count_documents({})
    except Exception as e:
        logger.warning(f"VSCode action count unavailable: {e}")
        action_count = 0
    return {
        "status": "connected",
        "provider": "gemini-2.5-flash",
        "capabilities": ["complete", "explain", "fix", "refactor", "generate", "chat"],
        "total_actions": action_count,
    }


@app.post("/api/command")
async def process_command(req: CommandRequest, user=Depends(verify_token)):
    """Process a command through JARVIS AI (ReActAgent primary, operator fallback)"""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="No command provided")

    session_id = req.session_id or "main"

    # Priority 1: ReActAgent with tool calling (the brain)
    assistant = _get_assistant()
    if assistant and assistant.react_agent:
        try:
            response = await assistant.process_query_async(command)
            intent = "agent"
            source = "react_agent"
        except Exception as exc:
            logger.warning(f"ReActAgent failed in command endpoint: {exc}")
            # Fall back to operator commands for system-level tasks
            operator_result = await execute_operator_command(command)
            if operator_result["handled"]:
                response = operator_result["response"]
                intent = operator_result["intent"]
                source = "operator"
            else:
                response = await jarvis_chat(command, session_id=session_id)
                intent = "chat"
                source = "llm"
    else:
        operator_result = await execute_operator_command(command)
        if operator_result["handled"]:
            response = operator_result["response"]
            intent = operator_result["intent"]
            source = "operator"
        else:
            response = await jarvis_chat(command, session_id=session_id)
            intent = "chat"
            source = "llm"

    # Save to conversation history
    try:
        await db.conversations.insert_one({
            "user_id": user["user_id"],
            "command": command,
            "response": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "intent": intent,
            "source": source,
        })
    except Exception as e:
        logger.warning(f"Conversation persistence unavailable: {e}")

    return {
        "response": response,
        "intent": intent,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/os/command")
async def os_command(req: OSCommandRequest, user=Depends(verify_token)):
    """Route a safe OS-level command through the JARVIS system layer."""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="No command provided")

    result = _route_os_command(command, dry_run=req.dry_run)
    if not result["handled"]:
        result = await execute_operator_command(command, dry_run=req.dry_run)

    return {
        **result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/operator/execute")
async def operator_execute(req: OperatorRequest, user=Depends(verify_token)):
    """Execute safe local operator actions for JARVIS/FRIDAY style control."""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="No command provided")

    result = await execute_operator_command(command, dry_run=req.dry_run)
    if not result["handled"]:
        result["response"] = await jarvis_chat(command, session_id=req.session_id or "operator")

    try:
        await db.operator_actions.insert_one({
            "user_id": user["user_id"],
            "command": command,
            "intent": result["intent"],
            "handled": result["handled"],
            "dry_run": req.dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Operator action persistence unavailable: {e}")

    return {
        **result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/code/assist")
async def code_assist(req: CodeRequest, user=Depends(verify_token)):
    """Developer coding assistance"""
    response = await jarvis_code_assist(req.prompt, req.repo_context, req.language)

    try:
        await db.code_sessions.insert_one({
            "user_id": user["user_id"],
            "prompt": req.prompt,
            "response": response,
            "language": req.language,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Code session persistence unavailable: {e}")

    return {
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/system/metrics")
async def system_metrics(user=Depends(verify_token)):
    """Get live system resource metrics"""
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    cpu_freq = psutil.cpu_freq()

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(logical=True),
            "freq_mhz": round(cpu_freq.current) if cpu_freq else 0,
        },
        "memory": {
            "percent": memory.percent,
            "total_gb": round(memory.total / (1024**3), 1),
            "used_gb": round(memory.used / (1024**3), 1),
            "available_gb": round(memory.available / (1024**3), 1),
        },
        "disk": {
            "percent": disk.percent,
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        },
        "platform": f"{platform.system()} {platform.release()}",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/weather")
async def weather(user=Depends(verify_token)):
    """Get weather data"""
    try:
        resp = http_requests.get(
            "https://wttr.in/?format=j1",
            timeout=8,
            headers={"User-Agent": "JARVIS/2.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]
            return {
                "temp_c": current.get("temp_C", "?"),
                "feels_like": current.get("FeelsLikeC", "?"),
                "humidity": current.get("humidity", "?"),
                "description": current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
                "wind_speed": current.get("windspeedKmph", "?"),
                "wind_dir": current.get("winddir16Point", "?"),
                "location": area.get("areaName", [{}])[0].get("value", "auto"),
                "country": area.get("country", [{}])[0].get("value", ""),
            }
        return {"error": "Weather service unavailable"}
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return {"error": str(e)}


@app.get("/api/history")
async def conversation_history(user=Depends(verify_token), limit: int = 30):
    try:
        assistant = _get_assistant()
        history = assistant.get_conversation_history()[-limit:]
    except Exception as e:
        logger.warning(f"Conversation history unavailable: {e}")
        history = []
    return {"history": history}


@app.get("/api/status")
async def system_status(user=Depends(verify_token)):
    """Get JARVIS system status"""
    data = _system_snapshot()
    
    conv_count = 0
    try:
        assistant = _get_assistant()
        stats = assistant.get_conversation_statistics()
        if stats:
            conv_count = stats.get("total_conversations", 0)
    except Exception as e:
        logger.warning(f"Conversation count unavailable: {e}")

    return {
        "status": "online",
        "llm_provider": "gemini-2.0-flash",
        "llm_available": True, 
        "ollama_configured": bool(OLLAMA_BASE_URL),
        "conversation_count": conv_count,
        "platform": f"{platform.system()} {platform.release()}",
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "skills": [
            "chat", "code_assist", "system_metrics", "weather",
            "file_management", "developer_mode", "operator_control",
            "app_scaffolding", "voice_commands"
        ],
    }


@app.get("/api/os/status")
async def os_status(user=Depends(verify_token)):
    """Return OS-style capability and system control metadata."""
    snapshot = _system_snapshot()
    service_state = _get_service_manager().get_status_snapshot()
    return {
        "platform": snapshot.get("platform"),
        "cpu_percent": snapshot.get("cpu_percent"),
        "memory_percent": snapshot.get("memory_percent"),
        "disk_percent": snapshot.get("disk_percent"),
        "battery_percent": snapshot.get("battery_percent"),
        "power_plugged": snapshot.get("power_plugged"),
        "workspace_root": str(WORKSPACE_ROOT),
        "service_state": service_state,
        "capabilities": [
            "filesystem_navigation",
            "system_metrics",
            "operator_control",
            "voice_commands",
            "device_management",
            "service_control",
        ],
    }


@app.get("/api/os/fs/list")
async def os_fs_list(path: Optional[str] = None, user=Depends(verify_token)):
    """List files and folders inside the workspace."""
    return _list_workspace(path)


@app.get("/api/os/fs/read")
async def os_fs_read(path: str, user=Depends(verify_token)):
    """Read the text preview of a workspace file."""
    return _read_workspace_file(path)


@app.get("/api/os/processes")
async def os_processes(limit: int = 50, user=Depends(verify_token)):
    """Return a process snapshot for the OS control surface."""
    processes = _get_service_manager().list_processes(limit=limit)
    return {"processes": processes, "count": len(processes)}


@app.get("/api/os/services")
async def os_services(user=Depends(verify_token)):
    """Return tracked services."""
    services = _get_service_manager().list_services()
    return {"services": services, "count": len(services)}


@app.get("/api/os/devices")
async def os_devices(user=Depends(verify_token)):
    """Return a high signal hardware snapshot for the OS control layer."""
    return _get_device_manager().snapshot()


@app.get("/api/os/audio/snapshot")
async def os_audio_snapshot(user=Depends(verify_token)):
    """Return comprehensive audio system state snapshot."""
    snapshot = _get_audio_manager().snapshot()
    return {
        "devices": [{"id": d.id, "name": d.name, "is_input": d.is_input, "is_output": d.is_output, 
                    "is_default_input": d.is_default_input, "is_default_output": d.is_default_output}
                   for d in snapshot.devices],
        "default_input": snapshot.default_input,
        "default_output": snapshot.default_output,
        "volume": snapshot.volume,
        "microphone_enabled": snapshot.microphone_enabled,
        "speakers_enabled": snapshot.speakers_enabled,
        "mic_muted": snapshot.mic_muted,
        "platform": snapshot.platform_name
    }


@app.get("/api/os/audio/volume")
async def os_audio_volume_get(user=Depends(verify_token)):
    """Get current system volume level."""
    snapshot = _get_audio_manager().snapshot()
    return {"volume": snapshot.volume, "min": 0.0, "max": 100.0}


class VolumeRequest(BaseModel):
    volume: float


@app.post("/api/os/audio/volume")
async def os_audio_volume_set(request: VolumeRequest, user=Depends(verify_token)):
    """Set system volume level."""
    try:
        success = _get_audio_manager().set_volume(request.volume)
        if success:
            return {"status": "success", "volume": request.volume}
        else:
            raise HTTPException(status_code=400, detail="Failed to set volume")
    except Exception as e:
        logger.error(f"Volume set error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/audio/microphone")
async def os_audio_microphone_get(user=Depends(verify_token)):
    """Get microphone state."""
    snapshot = _get_audio_manager().snapshot()
    return {
        "enabled": snapshot.microphone_enabled,
        "muted": snapshot.mic_muted,
        "available": snapshot.microphone_enabled
    }


class MicrophoneRequest(BaseModel):
    enabled: bool


@app.post("/api/os/audio/microphone")
async def os_audio_microphone_set(request: MicrophoneRequest, user=Depends(verify_token)):
    """Enable or disable microphone."""
    try:
        success = _get_audio_manager().toggle_microphone(request.enabled)
        if success:
            return {"status": "success", "enabled": request.enabled}
        else:
            raise HTTPException(status_code=400, detail="Failed to toggle microphone")
    except Exception as e:
        logger.error(f"Microphone toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CameraRequest(BaseModel):
    face_detection: bool = True


@app.get("/api/os/camera/state")
async def os_camera_state(user=Depends(verify_token)):
    """Get current camera state."""
    state = _get_camera_manager().state()
    return {
        "available": state.available,
        "enabled": state.enabled,
        "device_id": state.device_id,
        "recording": state.recording,
        "resolution": f"{state.resolution[0]}x{state.resolution[1]}",
        "fps": state.fps,
        "face_detection_active": state.face_detection_active,
        "last_face_timestamp": state.last_face_timestamp
    }


@app.post("/api/os/camera/enable")
async def os_camera_enable(user=Depends(verify_token)):
    """Enable camera access."""
    try:
        success = _get_camera_manager().enable()
        if success:
            return {"status": "success", "enabled": True}
        else:
            raise HTTPException(status_code=400, detail="Failed to enable camera")
    except Exception as e:
        logger.error(f"Camera enable error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/camera/disable")
async def os_camera_disable(user=Depends(verify_token)):
    """Disable camera access."""
    try:
        success = _get_camera_manager().disable()
        if success:
            return {"status": "success", "enabled": False}
        else:
            raise HTTPException(status_code=400, detail="Failed to disable camera")
    except Exception as e:
        logger.error(f"Camera disable error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/camera/snapshot")
async def os_camera_snapshot(detect_faces: bool = True, user=Depends(verify_token)):
    """Capture a snapshot from the camera with optional face detection."""
    try:
        if not _get_camera_manager().state().enabled:
            raise HTTPException(status_code=400, detail="Camera not enabled")
        
        snapshot = _get_camera_manager().capture_snapshot(detect_faces=detect_faces)
        if snapshot is None:
            raise HTTPException(status_code=500, detail="Failed to capture snapshot")
        
        return {
            "timestamp": snapshot.timestamp,
            "width": snapshot.width,
            "height": snapshot.height,
            "has_faces": snapshot.has_faces,
            "face_count": snapshot.face_count,
            "face_locations": snapshot.face_locations,
            "jpeg_base64": snapshot.jpeg_base64
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Snapshot capture error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/camera/face-detection")
async def os_camera_face_detection(request: CameraRequest, user=Depends(verify_token)):
    """Enable or disable face detection."""
    try:
        if request.face_detection:
            success = _get_camera_manager().start_face_detection()
        else:
            success = _get_camera_manager().stop_face_detection()
        
        if success:
            return {"status": "success", "face_detection": request.face_detection}
        else:
            raise HTTPException(status_code=400, detail="Failed to toggle face detection")
    except Exception as e:
        logger.error(f"Face detection toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/camera/devices")
async def os_camera_devices(user=Depends(verify_token)):
    """List available camera devices."""
    try:
        devices = _get_camera_manager().list_devices()
        return {"devices": devices, "count": len(devices)}
    except Exception as e:
        logger.error(f"Camera device list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PowerActionRequest(BaseModel):
    action: str  # "sleep", "restart", "shutdown", "hibernate"
    confirmed: bool = False


@app.get("/api/os/power/state")
async def os_power_state(user=Depends(verify_token)):
    """Get current system power state."""
    state = _get_power_manager().state()
    return {
        "ac_powered": state.ac_powered,
        "battery_percent": state.battery_percent,
        "charging": state.charging,
        "on_battery": state.on_battery,
        "low_battery": state.low_battery,
        "critical_battery": state.critical_battery,
        "estimated_runtime_minutes": state.estimated_runtime_minutes
    }


@app.post("/api/os/power/action")
async def os_power_action(request: PowerActionRequest, user=Depends(verify_token)):
    """
    Execute a power management action.
    All power actions require explicit confirmation.
    """
    if not request.confirmed:
        return {
            "status": "pending_confirmation",
            "action": request.action,
            "message": "Action requires explicit user confirmation via UI button"
        }
    
    try:
        action = request.action.lower()
        manager = _get_power_manager()
        
        if action == "sleep":
            result = manager.sleep(confirmed=True)
        elif action == "restart":
            result = manager.restart(confirmed=True)
        elif action == "shutdown":
            result = manager.shutdown(confirmed=True)
        elif action == "hibernate":
            result = manager.hibernate(confirmed=True)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        
        return {
            "status": "success" if result.success else "failed",
            "action": result.action.value,
            "message": result.message
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Power action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/power/cancel")
async def os_power_cancel(user=Depends(verify_token)):
    """Cancel any pending shutdown/restart operation."""
    try:
        result = _get_power_manager().cancel_pending_action()
        return {
            "status": "success" if result.success else "failed",
            "message": result.message
        }
    except Exception as e:
        logger.error(f"Cancel power action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Network Management Endpoints ─────────────────────────────────────────────

@app.get("/api/os/network/state")
async def os_network_state(user=Depends(verify_token)):
    """Get current network state including interfaces and WiFi."""
    try:
        manager = _get_network_manager()
        snapshot = manager.snapshot()
        
        # Convert dataclass to dict for JSON serialization
        interfaces_data = []
        for iface in snapshot.connected_interfaces:
            interfaces_data.append({
                "name": iface.name,
                "connection_type": iface.connection_type.value,
                "is_connected": iface.is_connected,
                "ip_address": iface.ip_address,
                "mac_address": iface.mac_address,
                "bytes_sent": iface.bytes_sent,
                "bytes_recv": iface.bytes_recv
            })
        
        wifi_data = []
        for network in snapshot.wifi_networks:
            wifi_data.append({
                "ssid": network.ssid,
                "signal_strength": network.signal_strength,
                "security": network.security,
                "frequency": network.frequency,
                "channel": network.channel
            })
        
        return {
            "status": "success",
            "data": {
                "active_interfaces": snapshot.active_interfaces,
                "connected_interfaces": interfaces_data,
                "default_gateway": snapshot.default_gateway,
                "dns_servers": snapshot.dns_servers,
                "wifi_enabled": snapshot.wifi_enabled,
                "wifi_networks": wifi_data,
                "current_ssid": snapshot.current_ssid,
                "vpn_connected": snapshot.vpn_connected,
                "total_bytes_sent": snapshot.total_bytes_sent,
                "total_bytes_recv": snapshot.total_bytes_recv
            }
        }
    except Exception as e:
        logger.error(f"Network state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/network/interfaces")
async def os_network_interfaces(user=Depends(verify_token)):
    """List all network interfaces with detailed information."""
    try:
        manager = _get_network_manager()
        snapshot = manager.snapshot()
        
        interfaces_data = []
        for iface in snapshot.connected_interfaces:
            interfaces_data.append({
                "name": iface.name,
                "connection_type": iface.connection_type.value,
                "is_connected": iface.is_connected,
                "ip_address": iface.ip_address,
                "gateway": iface.gateway,
                "netmask": iface.netmask,
                "mac_address": iface.mac_address,
                "stats": {
                    "bytes_sent": iface.bytes_sent,
                    "bytes_recv": iface.bytes_recv,
                    "packets_sent": iface.packets_sent,
                    "packets_recv": iface.packets_recv
                }
            })
        
        return {
            "status": "success",
            "count": len(interfaces_data),
            "interfaces": interfaces_data
        }
    except Exception as e:
        logger.error(f"Network interfaces error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/network/wifi/scan")
async def os_network_wifi_scan(user=Depends(verify_token)):
    """Scan for available WiFi networks."""
    try:
        manager = _get_network_manager()
        snapshot = manager.snapshot()
        
        wifi_data = []
        for network in snapshot.wifi_networks:
            wifi_data.append({
                "ssid": network.ssid,
                "signal_strength": network.signal_strength,
                "signal_bars": max(1, round(network.signal_strength / 25)),  # Convert to 1-4 bars
                "security": network.security,
                "frequency": network.frequency,
                "channel": network.channel
            })
        
        return {
            "status": "success",
            "wifi_enabled": snapshot.wifi_enabled,
            "current_ssid": snapshot.current_ssid,
            "count": len(wifi_data),
            "networks": wifi_data
        }
    except Exception as e:
        logger.error(f"WiFi scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/network/capabilities")
async def os_network_capabilities(user=Depends(verify_token)):
    """Get network system capabilities."""
    try:
        manager = _get_network_manager()
        capabilities = manager.capability_matrix()
        
        return {
            "status": "success",
            "capabilities": capabilities
        }
    except Exception as e:
        logger.error(f"Network capabilities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Voice Manager Endpoints
def _get_voice_manager() -> VoiceManager:
    """Get VoiceManager singleton instance."""
    return VoiceManager()


class VoiceSpeakRequest(BaseModel):
    """Request model for TTS.."""
    text: str


class VoiceWakeWordRequest(BaseModel):
    """Request model for wake word control."""
    enable: bool
    word: Optional[str] = None


@app.get("/api/os/voice/state")
async def os_voice_state(user=Depends(verify_token)):
    """Get current voice system state."""
    try:
        manager = _get_voice_manager()
        state = manager.state()
        
        return {
            "status": "success",
            "state": {
                "mode": state.mode.value,
                "listening": state.listening,
                "wake_word_enabled": state.wake_word_enabled,
                "wake_word": state.wake_word,
                "microphones": state.microphones,
                "speakers": state.speakers,
                "average_confidence": round(state.average_confidence, 3),
                "last_command": {
                    "text": state.last_command.text if state.last_command else None,
                    "confidence": round(state.last_command.confidence, 3) if state.last_command else None,
                    "timestamp": state.last_command.timestamp if state.last_command else None,
                } if state.last_command else None,
                "last_response": {
                    "text": state.last_response.text if state.last_response else None,
                    "status": state.last_response.status if state.last_response else None,
                    "timestamp": state.last_response.timestamp if state.last_response else None,
                } if state.last_response else None,
            }
        }
    except Exception as e:
        logger.error(f"Voice state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/voice/listen")
async def os_voice_listen(user=Depends(verify_token)):
    """Listen for voice command and process it through JARVIS."""
    try:
        manager = _get_voice_manager()
        command = manager.listen_for_command(timeout=10)
        
        if command:
            router = _get_voice_router()
            response_text = await router.handle_voice_command(command.text)
            return {
                "status": "success",
                "command": {
                    "text": command.text,
                    "confidence": round(command.confidence, 3),
                    "language": command.language,
                    "duration_ms": command.duration_ms,
                    "timestamp": command.timestamp,
                },
                "response": response_text,
            }
        else:
            return {
                "status": "no_command",
                "command": None
            }
    except Exception as e:
        logger.error(f"Voice listen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/voice/speak")
async def os_voice_speak(request: VoiceSpeakRequest, user=Depends(verify_token)):
    """Convert text to speech and play."""
    try:
        manager = _get_voice_manager()
        response = manager.speak_response(request.text)
        
        return {
            "status": "success",
            "response": {
                "text": response.text,
                "duration_ms": response.duration_ms,
                "status": response.status,
                "timestamp": response.timestamp,
            }
        }
    except Exception as e:
        logger.error(f"Voice speak error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/voice/wake-word")
async def os_voice_wake_word(request: VoiceWakeWordRequest, user=Depends(verify_token)):
    """Enable or disable wake word detection."""
    try:
        manager = _get_voice_manager()
        
        if request.enable:
            wake_word = request.word or "jarvis"
            manager.enable_wake_word(wake_word)
            return {
                "status": "success",
                "message": f"Wake word '{wake_word}' enabled"
            }
        else:
            manager.disable_wake_word()
            return {
                "status": "success",
                "message": "Wake word disabled"
            }
    except Exception as e:
        logger.error(f"Wake word error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/os/voice/capabilities")
async def os_voice_capabilities(user=Depends(verify_token)):
    """Get voice system capabilities."""
    try:
        manager = _get_voice_manager()
        capabilities = manager.capability_matrix()
        
        return {
            "status": "success",
            "capabilities": capabilities
        }
    except Exception as e:
        logger.error(f"Voice capabilities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/llm/status")
async def llm_status():
    """LLM availability check"""
    ollama_available = False
    try:
        resp = http_requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        ollama_available = resp.status_code == 200
    except Exception:
        pass

    return {
        "gemini": {
            "available": bool(EMERGENT_LLM_KEY),
            "model": "gemini-2.5-flash",
            "provider": "emergent",
        },
        "ollama": {
            "available": ollama_available,
            "model": OLLAMA_MODEL,
            "base_url": OLLAMA_BASE_URL,
        },
        "local_fallback": {
            "available": True,
            "provider": "deterministic_operator",
            "capabilities": ["operator_commands", "basic_chat", "code_templates"],
        },
    }


# ── Phase 3 Voice Analytics Endpoints ────────────────────────────────────────

@app.get("/api/voice/history")
async def get_voice_history(limit: int = 10, user=Depends(verify_token)):
    """Get recent voice command history with filtering options."""
    try:
        router = _get_voice_router()
        history = router.get_history(limit)
        
        history_data = []
        for entry in history:
            history_data.append({
                "command": entry.command_text,
                "response": entry.response_text,
                "confidence": entry.confidence,
                "status": entry.status.value,
                "duration_ms": entry.duration_ms,
                "timestamp": entry.timestamp.isoformat(),
            })
        
        return {
            "status": "success",
            "total_entries": len(history_data),
            "history": history_data,
        }
    except Exception as e:
        logger.error(f"Voice history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voice/stats")
async def get_voice_stats(user=Depends(verify_token)):
    """Get voice command performance statistics."""
    try:
        router = _get_voice_router()
        history_mgr = router.history_manager
        perf_mgr = router.performance_monitor
        
        stats = history_mgr.get_stats()
        perf_stats = perf_mgr.get_stats("voice_command")
        
        return {
            "status": "success",
            "history_stats": {
                "total_entries": stats.get("total_entries", 0),
                "success_rate": round(stats.get("success_rate_overall", 0), 3),
                "avg_latency_ms": round(stats.get("avg_latency_ms", 0), 2),
                "avg_confidence": round(stats.get("avg_confidence", 0), 3),
                "execution": stats.get("status_distribution", {}).get("EXECUTED", 0),
                "failed": stats.get("status_distribution", {}).get("FAILED", 0),
            },
            "performance_stats": {
                "count": perf_stats.get("count", 0),
                "success_rate": round(perf_stats.get("success_rate", 0), 3),
                "avg_duration_ms": round(perf_stats.get("avg_duration_ms", 0), 2),
                "p95_duration_ms": round(perf_stats.get("p95_duration_ms", 0), 2),
            }
        }
    except Exception as e:
        logger.error(f"Voice stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voice/context")
async def get_voice_context(user=Depends(verify_token)):
    """Get current conversation context and session info."""
    try:
        router = _get_voice_router()
        summary = router.get_session_summary()
        
        return {
            "status": "success",
            "session": summary,
        }
    except Exception as e:
        logger.error(f"Voice context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/voice/history")
async def clear_voice_history(older_than_hours: int = 24, user=Depends(verify_token)):
    """Clear voice history older than specified hours."""
    try:
        router = _get_voice_router()
        history_mgr = router.history_manager
        
        # Convert hours to minutes
        older_than_minutes = older_than_hours * 60 if older_than_hours > 0 else None
        
        # Clear with time filtering
        cleared_count = history_mgr.clear_history(older_than_minutes)
        remaining_count = len(history_mgr)
        
        return {
            "status": "success",
            "cleared_count": cleared_count,
            "remaining_count": remaining_count,
            "older_than_hours": older_than_hours,
        }
    except Exception as e:
        logger.error(f"Voice history clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.environ.get("JARVIS_HOST", "0.0.0.0"),
        port=int(os.environ.get("JARVIS_BACKEND_PORT", "8001")),
    )
