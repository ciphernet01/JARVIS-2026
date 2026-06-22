"""
A.S.T.R.A OS - FastAPI Backend
Agentic Spatial Task Reasoning Architecture runtime API.
"""

import os
import sys
import asyncio
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

from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import cv2

load_dotenv()

# Import new JARVIS core
from core import ConfigManager, Assistant
from modules.skills import SkillFactory
from modules.services import get_device_manager, ServiceManager, AudioManager, CameraManager, PowerManager, NetworkManager, VoiceManager, SafetyManager, PackageManager, HardwareValidationManager, HardwareStressManager, OSPreferencesManager, SecurityAuditManager, PerformanceBaselineManager, FailoverDrillManager, ReleaseEvidenceManager, GestureManager, SystemManager
from modules.intelligence.memory_engine import MemoryEngine
from modules.services.proactive_service import ProactiveService
from modules.control import ControlBrokerClient, ControlBrokerError
from modules.llm.local_runtime import OpenAICompatibleManager

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
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8001,http://127.0.0.1:8001"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("JARVIS_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

# Session management
SESSION_TOKENS = {}
GESTURE_CLIENTS = set()

# Orchestration queue (in-memory lightweight implementation)
ORCHESTRATION_QUEUE: List[Dict[str, Any]] = []
ORCHESTRATION_QUEUE_LOCK = asyncio.Lock()
ORCHESTRATION_ACTIVE_TASK: Optional[Dict[str, Any]] = None
ORCHESTRATION_LOG: List[Dict[str, Any]] = []

# Face detection cascade
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

# Enrolled face storage (in MongoDB)
FACE_COLLECTION = "enrolled_faces"
MACRO_COLLECTION = "neural_macros"

app = FastAPI(title="A.S.T.R.A OS API", version="2026.05")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _runtime_metrics() -> Dict[str, Any]:
    """Return lightweight process and host metrics for health monitoring."""
    process = psutil.Process(os.getpid())
    memory = process.memory_info()
    cpu_percent = psutil.cpu_percent(interval=None)

    return {
        "status": "ok",
        "service": "jarvis-backend",
        "version": app.version,
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "process": {
            "pid": process.pid,
            "threads": process.num_threads(),
            "rss_mb": round(memory.rss / (1024**2), 2),
            "vms_mb": round(memory.vms / (1024**2), 2),
            "cpu_percent": round(cpu_percent, 2),
        },
        "system": {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "disk_percent": round(psutil.disk_usage(str(WORKSPACE_ROOT)).percent, 2),
        },
    }


async def _readiness_checks() -> Dict[str, Any]:
    """Run a small set of readiness checks for deployment targets."""
    checks: Dict[str, Dict[str, Any]] = {}

    try:
        assistant = _get_assistant()
        checks["assistant"] = {"ready": assistant is not None, "detail": "assistant initialized"}
    except Exception as exc:
        checks["assistant"] = {"ready": False, "detail": str(exc)}

    try:
        _get_voice_router()
        checks["voice_router"] = {"ready": True, "detail": "voice router initialized"}
    except Exception as exc:
        checks["voice_router"] = {"ready": False, "detail": str(exc)}

    try:
        await asyncio.wait_for(db.command("ping"), timeout=1.5)
        checks["database"] = {"ready": True, "detail": "mongodb reachable"}
    except Exception as exc:
        checks["database"] = {"ready": False, "detail": str(exc)}

    ready = all(item["ready"] for item in checks.values())
    payload = {
        "status": "ready" if ready else "degraded",
        "ready": ready,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return payload


@app.get("/health")
async def health():
    """Public liveness check for container and process supervision."""
    return {"status": "ok", "service": "jarvis-backend", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
async def ready():
    """Public readiness check for deployment and orchestration."""
    payload = await _readiness_checks()
    if not payload["ready"]:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/metrics")
async def metrics():
    """Public deployment metrics for monitoring systems."""
    return _runtime_metrics()


@app.on_event("startup")
async def startup_event():
    """Warm up assistant and voice router on server startup."""
    try:
        _get_assistant()
        _get_voice_router()
        # start orchestration background worker
        try:
            asyncio.create_task(_run_orchestration_queue_worker())
        except Exception:
            logger.warning("Failed to start orchestration worker")
        logger.info("JARVIS backend startup complete")
    except Exception as exc:
        logger.warning(f"Startup warmup failed: {exc}")


@app.on_event("shutdown")
async def shutdown_event():
    """Release runtime resources on shutdown."""
    try:
        client.close()
    except Exception as exc:
        logger.warning(f"Database shutdown cleanup failed: {exc}")

    try:
        assistant = _jarvis_assistant
        if assistant and hasattr(assistant, "close"):
            assistant.close()
    except Exception as exc:
        logger.warning(f"Assistant shutdown cleanup failed: {exc}")

# ── Initialize JARVIS Core (ReActAgent + LLMRouter) ─────────────────────────
_jarvis_assistant: Optional[Assistant] = None
_service_manager: Optional[ServiceManager] = None
_device_manager: Optional[DeviceManager] = None
_audio_manager: Optional[AudioManager] = None
_camera_manager: Optional[CameraManager] = None
_power_manager: Optional[PowerManager] = None
_network_manager: Optional[NetworkManager] = None
_safety_manager: Optional[SafetyManager] = None
_package_manager: Optional[PackageManager] = None
_hardware_validation_manager: Optional[HardwareValidationManager] = None
_hardware_stress_manager: Optional[HardwareStressManager] = None
_preferences_manager: Optional[OSPreferencesManager] = None
_security_audit_manager: Optional[SecurityAuditManager] = None
_performance_baseline_manager: Optional[PerformanceBaselineManager] = None
_failover_drill_manager: Optional[FailoverDrillManager] = None
_release_evidence_manager: Optional[ReleaseEvidenceManager] = None
_local_runtime: Optional[OpenAICompatibleManager] = None
_gesture_manager: Optional[GestureManager] = None
_system_manager: Optional[SystemManager] = None
_memory_engine: Optional[MemoryEngine] = None
_proactive_service: Optional[ProactiveService] = None
_voice_router = None
_voice_callbacks = None


def _get_network_manager() -> NetworkManager:
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager()
    return _network_manager


def _get_safety_manager() -> SafetyManager:
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager(workspace_root=str(WORKSPACE_ROOT))
    return _safety_manager


def _get_package_manager() -> PackageManager:
    global _package_manager
    if _package_manager is None:
        _package_manager = PackageManager()
    return _package_manager


def _get_hardware_validation_manager() -> HardwareValidationManager:
    global _hardware_validation_manager
    if _hardware_validation_manager is None:
        _hardware_validation_manager = HardwareValidationManager(workspace_root=str(WORKSPACE_ROOT))
    return _hardware_validation_manager


def _get_hardware_stress_manager() -> HardwareStressManager:
    global _hardware_stress_manager
    if _hardware_stress_manager is None:
        _hardware_stress_manager = HardwareStressManager(workspace_root=str(WORKSPACE_ROOT))
    return _hardware_stress_manager


def _get_preferences_manager() -> OSPreferencesManager:
    global _preferences_manager
    if _preferences_manager is None:
        _preferences_manager = OSPreferencesManager(workspace_root=str(WORKSPACE_ROOT))
    return _preferences_manager


def _get_security_audit_manager() -> SecurityAuditManager:
    global _security_audit_manager
    if _security_audit_manager is None:
        _security_audit_manager = SecurityAuditManager(workspace_root=str(WORKSPACE_ROOT))
    return _security_audit_manager


def _get_performance_baseline_manager() -> PerformanceBaselineManager:
    global _performance_baseline_manager
    if _performance_baseline_manager is None:
        _performance_baseline_manager = PerformanceBaselineManager(workspace_root=str(WORKSPACE_ROOT))
    return _performance_baseline_manager


def _get_failover_drill_manager() -> FailoverDrillManager:
    global _failover_drill_manager
    if _failover_drill_manager is None:
        _failover_drill_manager = FailoverDrillManager(
            workspace_root=str(WORKSPACE_ROOT),
            safety_manager=_get_safety_manager(),
            service_manager=_get_service_manager(),
        )
    return _failover_drill_manager


def _get_release_evidence_manager() -> ReleaseEvidenceManager:
    global _release_evidence_manager
    if _release_evidence_manager is None:
        _release_evidence_manager = ReleaseEvidenceManager(
            workspace_root=str(WORKSPACE_ROOT),
            security_manager=_get_security_audit_manager(),
            performance_manager=_get_performance_baseline_manager(),
            failover_manager=_get_failover_drill_manager(),
            hardware_validation_manager=_get_hardware_validation_manager(),
            hardware_stress_manager=_get_hardware_stress_manager(),
        )
    return _release_evidence_manager


def _get_gesture_manager() -> GestureManager:
    global _gesture_manager
    if _gesture_manager is None:
        _gesture_manager = GestureManager(workspace_root=str(WORKSPACE_ROOT))
        
        # Bridge gesture events to the global broadcast feed
        def on_gesture_event(event):
            asyncio.run_coroutine_threadsafe(
                broadcast_gesture_event(event.to_dict()),
                asyncio.get_event_loop()
            )
        
        # Register for ALL major gestures
        from modules.vision.gesture_engine import ALL_GESTURES
        for g in ALL_GESTURES:
            _gesture_manager.register_action_callback(_gesture_manager.get_action_map().get(g, {}).get("action"), on_gesture_event)
            
    return _gesture_manager


def _get_system_manager() -> SystemManager:
    global _system_manager
    if _system_manager is None:
        _system_manager = SystemManager()
    return _system_manager


def _get_local_runtime() -> OpenAICompatibleManager:
    global _local_runtime
    if _local_runtime is None:
        config = ConfigManager().llm
        _local_runtime = OpenAICompatibleManager(
            base_url=config.base_url,
            model=config.model,
            provider=config.provider,
            api_key=config.api_key or "local",
            temperature=config.temperature,
            top_p=config.top_p,
            timeout_seconds=config.timeout_seconds,
            system_prompt=config.system_prompt,
        )
    return _local_runtime


def _get_memory_engine() -> MemoryEngine:
    global _memory_engine
    if _memory_engine is None:
        _memory_engine = MemoryEngine(memory_path=str(STATE_ROOT / "memory" / "intelligence" / "episodic_memory.json"))
    return _memory_engine


def _get_proactive_service() -> ProactiveService:
    global _proactive_service
    if _proactive_service is None:
        _proactive_service = ProactiveService(_get_memory_engine())
        _proactive_service.start()
    return _proactive_service


def _get_assistant() -> Optional[Assistant]:
    global _jarvis_assistant
    if _jarvis_assistant is None:
        try:
            config = ConfigManager()
            skill_registry = SkillFactory.create_default_registry()

            # Setup persistence layer for the web backend (Absolute path)
            db_path = STATE_ROOT / "jarvis.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
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


def _get_voice_callbacks():
    """Get and register voice callbacks."""
    global _voice_callbacks
    if _voice_callbacks is None:
        from modules.agent.voice_router import VoiceCallbacks
        _voice_callbacks = VoiceCallbacks(_get_assistant(), _get_voice_manager())
        _voice_callbacks.register_all()
        logger.info("Voice callbacks registered with VoiceManager")
    return _voice_callbacks


def _get_service_manager() -> ServiceManager:
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager


def _get_device_manager():
    global _device_manager
    if _device_manager is None:
        # Let get_device_manager decide between simulated and real implementations
        _device_manager = get_device_manager()
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


class SafetyModeRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


class SafetyCheckpointRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""


class SafetyRestoreRequest(BaseModel):
    checkpoint_id: str
    dry_run: bool = True
    confirmed: bool = False


class MaintenanceCommandRequest(BaseModel):
    command: str
    timeout_seconds: int = 20


class PackageSearchRequest(BaseModel):
    query: str


class PackageActionRequest(BaseModel):
    action: str
    package: Optional[str] = None
    dry_run: bool = True
    confirmed: bool = False


class AppLaunchRequest(BaseModel):
    app: str
    dry_run: bool = True
    confirmed: bool = False


class ServiceActionRequest(BaseModel):
    action: str
    name: str
    command: Optional[str] = None
    directory: Optional[str] = None
    port: Optional[int] = None
    dry_run: bool = True
    confirmed: bool = False


class SystemServiceActionRequest(BaseModel):
    action: str
    name: str
    dry_run: bool = True
    confirmed: bool = False
    reason: str = ""


class HardwareValidationRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""
    save: bool = True


class HardwareStressRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""
    duration_seconds: float = 30.0
    interval_seconds: float = 2.0
    save: bool = True


class SecurityAuditRequest(BaseModel):
    save: bool = True


class PerformanceBaselineRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""
    duration_seconds: float = 30.0
    interval_seconds: float = 2.0
    save: bool = True


class FailoverDrillRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""
    save: bool = True


class ReleaseEvidenceRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = ""
    save: bool = True


class PreferencesUpdateRequest(BaseModel):
    language: Optional[str] = None
    tts_voice: Optional[str] = None
    high_contrast: Optional[bool] = None
    reduced_motion: Optional[bool] = None
    large_text: Optional[bool] = None
    scanlines: Optional[bool] = None
    telemetry_refresh_seconds: Optional[int] = None


class GestureActionMapUpdate(BaseModel):
    gesture: str
    action: str
    label: str = ""
    description: str = ""


class MemoryEntry(BaseModel):
    user: str
    assistant: str
    tags: Optional[List[str]] = None


class MacroStep(BaseModel):
    type: str  # "command", "app", "service", "wait"
    value: str
    params: Optional[Dict[str, Any]] = None

class MacroCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    steps: List[MacroStep]
    trigger_phrase: Optional[str] = None

class MacroExecuteRequest(BaseModel):
    macro_id: str


class OrchestrationTaskRequest(BaseModel):
    prompt: str
    label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ── Audit Logging Helper ───────────────────────────────────────────────────
def _audit_action(user: str, action: str, details: Optional[Dict[str, Any]] = None):
    """Record an action to the system audit log."""
    log_entry = {
        "timestamp": time.time(),
        "user": user,
        "action": action,
        "details": details or {}
    }
    logger.info(f"AUDIT: {user} performed {action} - {json.dumps(details or {})}")
    # Persist to local JSON log
    try:
        log_dir = WORKSPACE_ROOT / "memory" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "audit.json"
        
        # Read existing logs
        logs = []
        if log_file.exists():
            try:
                logs = json.loads(log_file.read_text(encoding="utf-8"))
            except Exception:
                logs = []
        
        # Append and keep last 1000
        logs.append(log_entry)
        log_file.write_text(json.dumps(logs[-1000:], indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to persist audit log: {exc}")


async def broadcast_gesture_event(event_dict: Dict[str, Any]):
    """Broadcast a gesture event to all connected WebSocket clients."""
    if not GESTURE_CLIENTS:
        return
    
    dead_clients = set()
    message = json.dumps({"type": "gesture", "data": event_dict})
    
    for client_ws in GESTURE_CLIENTS:
        try:
            await client_ws.send_text(message)
        except Exception:
            dead_clients.add(client_ws)
    
    for dead in dead_clients:
        GESTURE_CLIENTS.remove(dead)


@app.websocket("/ws/gestures")
async def gesture_websocket(websocket: WebSocket):
    await websocket.accept()
    GESTURE_CLIENTS.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        GESTURE_CLIENTS.remove(websocket)
    except Exception:
        if websocket in GESTURE_CLIENTS:
            GESTURE_CLIENTS.remove(websocket)


# ── Auth ─────────────────────────────────────────────────────────────────────
def verify_token(request: Request):
    token = request.headers.get("X-JARVIS-TOKEN")
    if not token or token not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized. Security protocol active.")
    return SESSION_TOKENS[token]


@app.get("/api/ai/runtime")
async def ai_runtime_capabilities(user=Depends(verify_token)):
    """Report the configured local inference runtime and its advertised models."""
    capabilities = await asyncio.to_thread(_get_local_runtime().capabilities)
    return capabilities.to_dict()


# Operator Core
CODE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = Path(os.environ.get("JARVIS_WORKSPACE", CODE_ROOT)).expanduser().resolve()
STATE_ROOT = Path(os.environ.get("ASTRA_STATE_DIR", WORKSPACE_ROOT)).expanduser().resolve()
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


def _audit_action(user: Optional[Dict[str, Any]], action: str, details: Optional[Dict[str, Any]] = None, success: bool = True) -> None:
    assistant = _get_assistant()
    audit_logger = getattr(assistant, "persistence", {}).get("audit_logger") if assistant else None
    if audit_logger:
        audit_logger.log_action(
            user_id=(user or {}).get("user_id"),
            action=action,
            details=details or {},
            success=success,
        )


def _orchestration_snapshot() -> Dict[str, Any]:
    return {
        "queue_depth": len(ORCHESTRATION_QUEUE),
        "active": ORCHESTRATION_ACTIVE_TASK,
        "log_tail": ORCHESTRATION_LOG[-10:],
    }


async def _enqueue_orchestration_task(task: Dict[str, Any]) -> None:
    async with ORCHESTRATION_QUEUE_LOCK:
        ORCHESTRATION_QUEUE.append(task)


async def _run_orchestration_queue_worker() -> None:
    """Background worker that processes orchestration tasks sequentially."""
    global ORCHESTRATION_ACTIVE_TASK
    while True:
        task = None
        async with ORCHESTRATION_QUEUE_LOCK:
            if ORCHESTRATION_QUEUE:
                task = ORCHESTRATION_QUEUE.pop(0)

        if not task:
            await asyncio.sleep(1.0)
            continue

        ORCHESTRATION_ACTIVE_TASK = {**task, "status": "running", "started_at": time.time()}
        ORCHESTRATION_LOG.append({"event": "task_started", "task": task, "ts": time.time()})

        try:
            assistant = _get_assistant()
            result = None
            if assistant:
                result = await assistant.process_query_async(task.get("prompt", ""))

            ORCHESTRATION_ACTIVE_TASK.update({"status": "complete", "result": result, "finished_at": time.time()})
            ORCHESTRATION_LOG.append({"event": "task_completed", "task": task, "result": str(result)[:1024], "ts": time.time()})
        except Exception as exc:
            ORCHESTRATION_ACTIVE_TASK.update({"status": "failed", "error": str(exc), "finished_at": time.time()})
            ORCHESTRATION_LOG.append({"event": "task_failed", "task": task, "error": str(exc), "ts": time.time()})
        finally:
            # keep small history
            ORCHESTRATION_LOG[:] = ORCHESTRATION_LOG[-100:]
            ORCHESTRATION_ACTIVE_TASK = None


def _safety_state_payload() -> Dict[str, Any]:
    manager = _get_safety_manager()
    state = manager.state()
    return {
        "status": "success",
        "state": {
            "safe_mode": state.safe_mode,
            "recovery_mode": state.recovery_mode,
            "maintenance_shell_available": state.maintenance_shell_available,
            "fallback_desktop_available": state.fallback_desktop_available,
            "backup_available": state.backup_available,
            "last_checkpoint_at": state.last_checkpoint_at,
            "checkpoint_count": state.checkpoint_count,
            "permission_escalation_required": state.permission_escalation_required,
            "safety_gates": state.safety_gates,
            "active_reasons": state.active_reasons,
            "platform": state.platform_name,
            "maintenance_allowlist": manager.maintenance_allowlist(),
        },
        "capabilities": manager.capability_matrix(),
    }


def _readiness_item(
    key: str,
    label: str,
    status: str,
    detail: str,
    action: Optional[str] = None,
    blocks_operation: Optional[bool] = None,
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "action": action,
        "blocks_operation": status == "fail" if blocks_operation is None else blocks_operation,
    }


def _os_readiness_payload() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    health = _system_snapshot()
    memory_ok = (health.get("memory_available_gb") or 0) >= 2
    disk_ok = (health.get("disk_free_gb") or 0) >= 10
    items.append(_readiness_item(
        "system_resources",
        "System Resources",
        "pass" if memory_ok and disk_ok else "warn",
        f"{health.get('memory_available_gb')} GB RAM free / {health.get('disk_free_gb')} GB disk free",
        "Close background apps or free storage" if not (memory_ok and disk_ok) else None,
    ))

    safety_state = _get_safety_manager().state()
    items.append(_readiness_item(
        "recovery_safety",
        "Recovery & Safety",
        "pass" if safety_state.checkpoint_count > 0 else "warn",
        f"{safety_state.checkpoint_count} recovery checkpoint(s), {len(safety_state.safety_gates)} gates active",
        "Create a recovery checkpoint" if safety_state.checkpoint_count == 0 else None,
    ))

    package_state = _get_package_manager().provider_state()
    items.append(_readiness_item(
        "package_lifecycle",
        "Package Lifecycle",
        "pass" if package_state.get("available") else "warn",
        package_state.get("message", "Package provider status unknown"),
        "Install winget/choco/brew/apt provider" if not package_state.get("available") else None,
    ))

    voice_caps = _get_voice_manager().capability_matrix()
    voice_ok = bool(voice_caps.get("stt_available") or voice_caps.get("tts_available"))
    voice_training = _get_voice_manager().training_plan().get("profile", {})
    voice_trained = voice_training.get("status") == "ready"
    items.append(_readiness_item(
        "voice_stack",
        "Voice Stack",
        "pass" if voice_ok and voice_trained else "warn",
        (
            f"STT {'ready' if voice_caps.get('stt_available') else 'limited'} / "
            f"TTS {'ready' if voice_caps.get('tts_available') else 'limited'} / "
            f"training {voice_training.get('status', 'not_started')}"
        ),
        "Complete voice training" if voice_ok and not voice_trained else "Install/configure voice dependencies" if not voice_ok else None,
    ))

    device_snapshot = _get_device_manager().snapshot()
    camera_available = bool(device_snapshot.get("camera", {}).get("available"))
    microphone_available = bool(device_snapshot.get("microphone", {}).get("available"))
    items.append(_readiness_item(
        "device_matrix",
        "Device Matrix",
        "pass" if camera_available and microphone_available else "warn",
        f"Camera {'ready' if camera_available else 'unavailable'} / Mic {'ready' if microphone_available else 'unavailable'}",
        "Check camera/microphone permissions" if not (camera_available and microphone_available) else None,
    ))

    hardware_reports = _get_hardware_validation_manager().list_reports(limit=1)
    items.append(_readiness_item(
        "hardware_validation",
        "Hardware Validation",
        "pass" if hardware_reports else "warn",
        "Latest hardware validation report found" if hardware_reports else "No hardware validation report captured yet",
        "Run hardware validation from Settings" if not hardware_reports else None,
    ))

    service_state = _get_service_manager().get_status_snapshot()
    items.append(_readiness_item(
        "service_lifecycle",
        "Service Lifecycle",
        "pass",
        f"{service_state.get('tracked_services')} tracked service(s), {service_state.get('running_processes')} processes visible",
    ))

    prefs = _get_preferences_manager().state()
    items.append(_readiness_item(
        "accessibility_preferences",
        "Accessibility & Language",
        "pass",
        f"{prefs.language}, contrast {'high' if prefs.high_contrast else 'standard'}, motion {'reduced' if prefs.reduced_motion else 'standard'}",
    ))

    security_reports = _get_security_audit_manager().list_reports(limit=1)
    latest_security = security_reports[0] if security_reports else None
    security_status = latest_security.get("overall_status") if latest_security else "warn"
    items.append(_readiness_item(
        "security_audit",
        "Security Audit",
        "pass" if security_status == "pass" else "fail" if security_status == "fail" else "warn",
        f"Latest audit {security_status} / score {latest_security.get('score')}" if latest_security else "No security hardening audit captured yet",
        "Run security audit" if not latest_security or security_status != "pass" else None,
        blocks_operation=False,
    ))

    performance_reports = _get_performance_baseline_manager().list_reports(limit=1)
    latest_performance = performance_reports[0] if performance_reports else None
    performance_status = latest_performance.get("overall_status") if latest_performance else "warn"
    items.append(_readiness_item(
        "performance_baseline",
        "Performance Baseline",
        "pass" if performance_status == "pass" else "fail" if performance_status == "fail" else "warn",
        (
            f"Latest baseline {performance_status} / memory growth "
            f"{latest_performance.get('summary', {}).get('rss_growth_mb')} MB"
        ) if latest_performance else "No performance baseline captured yet",
        "Run performance baseline" if not latest_performance or performance_status != "pass" else None,
        blocks_operation=False,
    ))

    failover_reports = _get_failover_drill_manager().list_reports(limit=1)
    latest_failover = failover_reports[0] if failover_reports else None
    failover_status = latest_failover.get("overall_status") if latest_failover else "warn"
    items.append(_readiness_item(
        "failover_drill",
        "Failover Drill",
        "pass" if failover_status == "pass" else "fail" if failover_status == "fail" else "warn",
        f"Latest drill {failover_status} / score {latest_failover.get('score')}" if latest_failover else "No failover drill captured yet",
        "Run failover drill" if not latest_failover or failover_status != "pass" else None,
        blocks_operation=False,
    ))

    evidence_bundles = _get_release_evidence_manager().list_bundles(limit=1)
    latest_evidence = evidence_bundles[0] if evidence_bundles else None
    evidence_status = latest_evidence.get("release_status") if latest_evidence else "warn"
    items.append(_readiness_item(
        "release_evidence",
        "Release Evidence",
        "pass" if evidence_status == "ready" else "fail" if evidence_status == "blocked" else "warn",
        f"Latest bundle {evidence_status} / score {latest_evidence.get('score')}" if latest_evidence else "No release-candidate evidence bundle captured yet",
        "Create release evidence bundle" if not latest_evidence or evidence_status != "ready" else None,
        blocks_operation=False,
    ))

    status_rank = {"fail": 0, "warn": 1, "pass": 2}
    score = round(sum(status_rank.get(item["status"], 0) for item in items) / (len(items) * 2), 2)
    release_blockers = [item for item in items if item["status"] == "fail"]
    operation_blockers = [item for item in release_blockers if item.get("blocks_operation")]
    warnings = [item for item in items if item["status"] == "warn"]
    operation_overall = "blocked" if operation_blockers else "ready_with_warnings" if warnings or release_blockers else "ready"

    return {
        "status": "success",
        "overall": operation_overall,
        "operation_status": operation_overall,
        "release_status": "blocked" if release_blockers else "ready_with_warnings" if warnings else "ready",
        "score": score,
        "items": items,
        "warnings": len(warnings),
        "blockers": len(release_blockers),
        "release_blockers": len(release_blockers),
        "operation_blockers": len(operation_blockers),
        "generated_at": datetime.now(timezone.utc).isoformat(),
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


def _allowed_apps_payload() -> List[Dict[str, Any]]:
    apps = []
    seen = set()
    for alias, executable in APP_ALLOWLIST.items():
        canonical = executable.lower()
        if canonical in seen:
            continue
        seen.add(canonical)
        available = bool(shutil.which(executable)) or executable.endswith(".exe") or executable.endswith(".cmd")
        apps.append({
            "id": alias,
            "label": alias.title(),
            "executable": executable,
            "available": available,
        })
    return sorted(apps, key=lambda item: item["label"])


def _launch_allowed_app(app_name: str, dry_run: bool = True, confirmed: bool = False) -> Dict[str, Any]:
    app_key = app_name.strip().lower()
    if app_key not in APP_ALLOWLIST:
        raise HTTPException(status_code=400, detail="App is not in the operator allowlist")
    executable = APP_ALLOWLIST[app_key]
    resolved = shutil.which(executable) or executable
    requires_confirmation = True
    if dry_run:
        return {
            "success": True,
            "app": app_key,
            "executable": executable,
            "resolved": resolved,
            "dry_run": True,
            "requires_confirmation": True,
            "message": "App launch plan ready.",
        }
    if requires_confirmation and not confirmed:
        return {
            "success": False,
            "app": app_key,
            "executable": executable,
            "resolved": resolved,
            "dry_run": dry_run,
            "requires_confirmation": True,
            "message": "Confirmation required before launching app.",
        }
    subprocess.Popen([resolved], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
    return {
        "success": True,
        "app": app_key,
        "executable": executable,
        "resolved": resolved,
        "dry_run": False,
        "requires_confirmation": False,
        "message": f"Launched {app_key}.",
    }


def _service_action_payload(result: Dict[str, Any], action: str, dry_run: bool = False) -> Dict[str, Any]:
    return {
        "success": bool(result.get("success")),
        "action": action,
        "dry_run": dry_run,
        "message": result.get("output") if result.get("success") else result.get("error"),
        "data": result.get("output") if isinstance(result.get("output"), dict) else {},
        "error": result.get("error"),
    }


def _run_service_action(request: ServiceActionRequest) -> Dict[str, Any]:
    manager = _get_service_manager()
    action = request.action.strip().lower()
    name = _safe_name(request.name, default="jarvis-service")
    safety = _get_safety_manager().state()

    if action in {"start", "restart"} and (safety.safe_mode or safety.recovery_mode):
        reason = "Safe mode blocks service start/restart" if safety.safe_mode else "Recovery mode blocks service start/restart"
        return {"success": False, "action": action, "dry_run": request.dry_run, "message": reason, "data": {}, "error": reason}

    if action == "start":
        if not request.command:
            return {"success": False, "action": action, "dry_run": request.dry_run, "message": "Service command is required.", "data": {}, "error": "Service command is required."}
        directory = str(_resolve_workspace_path(request.directory)) if request.directory else str(WORKSPACE_ROOT)
        if request.dry_run:
            return {
                "success": True,
                "action": action,
                "dry_run": True,
                "message": "Service start plan ready.",
                "data": {"name": name, "command": request.command, "directory": directory, "port": request.port},
                "error": None,
            }
        if not request.confirmed:
            return {
                "success": False,
                "action": action,
                "dry_run": request.dry_run,
                "message": "Confirmation required before starting service.",
                "data": {"name": name, "command": request.command, "directory": directory, "port": request.port},
                "error": None,
            }
        return _service_action_payload(manager.start(name, request.command, directory, request.port), action, False)

    if action == "stop":
        if request.dry_run:
            return {"success": True, "action": action, "dry_run": True, "message": "Service stop plan ready.", "data": {"name": name}, "error": None}
        if not request.confirmed:
            return {"success": False, "action": action, "dry_run": False, "message": "Confirmation required before stopping service.", "data": {"name": name}, "error": None}
        return _service_action_payload(manager.stop(name), action, False)

    if action == "restart":
        if request.dry_run:
            return {"success": True, "action": action, "dry_run": True, "message": "Service restart plan ready.", "data": {"name": name}, "error": None}
        if not request.confirmed:
            return {"success": False, "action": action, "dry_run": False, "message": "Confirmation required before restarting service.", "data": {"name": name}, "error": None}
        return _service_action_payload(manager.restart(name), action, False)

    if action == "status":
        return _service_action_payload(manager.status(name), action, False)

    return {"success": False, "action": action, "dry_run": request.dry_run, "message": f"Unsupported service action: {action}", "data": {}, "error": "Unsupported service action"}


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
        "system": "A.S.T.R.A OS",
        "version": "2026.05",
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/orchestration/queue")
async def get_orchestration_queue(user=Depends(verify_token)):
    """Return a snapshot of the orchestration queue and active task."""
    return {"queue": ORCHESTRATION_QUEUE, "snapshot": _orchestration_snapshot()}


@app.post("/api/orchestration/queue")
async def post_orchestration_queue(req: OrchestrationTaskRequest, user=Depends(verify_token)):
    """Enqueue a new orchestration task for the background worker."""
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "prompt": req.prompt,
        "label": req.label or (req.prompt[:80] + ("..." if len(req.prompt) > 80 else "")),
        "metadata": req.metadata or {},
        "status": "queued",
        "created_at": time.time(),
    }

    await _enqueue_orchestration_task(task)
    _audit_action(user, "enqueue_orchestration_task", {"task_id": task_id, "label": task.get("label")})
    return {"id": task_id}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Biometric face verification login - checks against imagedata/ folder and enrolled faces"""
    face_detected = False
    face_confidence = 0.0
    face_box = None  # {x, y, w, h} for frontend to draw rectangle
    verification_method = req.method
    identified_user_id = "shrey_ceo"
    identified_user_name = "Sir"

    if req.method in {"camera_unavailable", "production_bypass"} and not req.image:
        verification_method = "camera_unavailable_bypass"

    if req.method == "neural_key" and getattr(req, 'key', None):
        # Neural Key (Password) logic
        # For Market Ready OS, we match against a system-wide override or per-user vault
        verification_method = "neural_key_verified"
        face_detected = False
        face_confidence = 1.0

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
                                # Check for name in filename like "tony_stark.jpg"
                                name_part = ref_path.stem.replace('_', ' ').title()
                                identified_user_name = name_part
                                identified_user_id = ref_path.stem.lower()
                        except Exception:
                            continue

                    # Method 2: Check MongoDB enrolled faces (all enrolled users)
                    async for enrolled in db[FACE_COLLECTION].find({}):
                        stored_hist = np.array(enrolled["histogram"], dtype=np.float32)
                        score = cv2.compareHist(candidate_hist, stored_hist, cv2.HISTCMP_CORREL)
                        if score > best_score:
                            best_score = score
                            matched_against = f"enrolled:{enrolled['label']}"
                            identified_user_id = enrolled.get("user_id", "unknown_user")
                            identified_user_name = enrolled.get("label", "Unknown").title()

                    face_confidence = max(0.0, best_score)

                    # If we have reference data and score is too low, deny
                    if (ref_paths or await db[FACE_COLLECTION].count_documents({})) and best_score < 0.3:
                        return {
                            "success": False,
                            "message": f"Face not recognized. Similarity: {best_score:.2f}. Access denied.",
                            "face_detected": True,
                            "face_box": face_box,
                            "confidence": face_confidence,
                        }

                    # If no reference data exists, accept any face
                    if not ref_paths and not await db[FACE_COLLECTION].count_documents({}):
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
        "user_id": identified_user_id,
        "user_name": identified_user_name,
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

    message = f"Biometric verification complete. Welcome back, {identified_user_name}."
    if face_detected:
        message = f"Face recognized (confidence: {face_confidence:.0%}). Welcome back, {identified_user_name}."
    elif verification_method == "camera_unavailable_bypass":
        message = f"Camera offline. Production bypass authorized. Welcome back, {identified_user_name}."

    # Update assistant context to the identified user
    assistant = _get_assistant()
    if assistant:
        assistant.set_current_user(identified_user_id)
        assistant.set_user_context("user_name", identified_user_name)

    return {
        "success": True,
        "token": token,
        "message": message,
        "user": {"name": identified_user_name, "id": identified_user_id},
        "face_detected": face_detected,
        "face_box": face_box,
        "confidence": face_confidence,
    }


@app.post("/api/auth/dev_token")
async def dev_token():
    """Development helper: return a pre-authorized session token for local dev testing.
    This is intentionally permissive and only meant for local development environments.
    """
    token = str(uuid.uuid4())
    user_data = {
        "user_id": "dev_user",
        "user_name": "Developer",
        "login_time": datetime.now(timezone.utc).isoformat(),
        "method": "dev_token",
        "face_detected": False,
        "face_confidence": 1.0,
    }
    SESSION_TOKENS[token] = user_data
    try:
        await db.sessions.insert_one({
            "token": token,
            "user_id": user_data["user_id"],
            "login_time": user_data["login_time"],
            "method": "dev_token",
        })
    except Exception:
        # ignore persistence failures
        pass
    return {"token": token, "message": "Development token issued."}


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

    assistant = None
    assistant_status: Dict[str, Any] = {}
    try:
        assistant = _get_assistant()
        if assistant:
            assistant_status = assistant.get_status() or {}
    except Exception as e:
        logger.warning(f"Assistant status unavailable: {e}")
    
    conv_count = 0
    try:
        if assistant:
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
        "agent_enabled": assistant_status.get("agent_enabled", False),
        "react_agent_enabled": assistant_status.get("react_agent_enabled", False),
        "llm_router_enabled": assistant_status.get("llm_router_enabled", False),
        "project_index_enabled": assistant_status.get("project_index_enabled", False),
        "orchestration_ready": bool(assistant_status.get("agent_enabled") or assistant_status.get("react_agent_enabled")),
        "orchestration": _orchestration_snapshot(),
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
            "recovery_safety",
            "package_lifecycle",
        ],
    }


@app.get("/api/os/readiness")
async def os_readiness(user=Depends(verify_token)):
    """Return first-run operating system readiness checklist."""
    return _os_readiness_payload()


@app.get("/api/os/preferences")
async def os_preferences(user=Depends(verify_token)):
    """Return persisted language, accessibility, and UI preferences."""
    manager = _get_preferences_manager()
    return {
        "status": "success",
        "preferences": manager.state().__dict__,
        "capabilities": manager.capabilities(),
    }


@app.post("/api/os/preferences")
async def os_preferences_update(request: PreferencesUpdateRequest, user=Depends(verify_token)):
    """Update persisted language, accessibility, and UI preferences."""
    manager = _get_preferences_manager()
    changes = request.dict(exclude_unset=True)
    prefs = manager.update(changes, datetime.now(timezone.utc).isoformat())
    _audit_action(user, "os_preferences_update", changes, success=True)
    return {
        "status": "success",
        "preferences": prefs.__dict__,
        "capabilities": manager.capabilities(),
        "message": "OS preferences updated.",
    }


@app.post("/api/os/preferences/reset")
async def os_preferences_reset(user=Depends(verify_token)):
    """Reset language, accessibility, and UI preferences to defaults."""
    manager = _get_preferences_manager()
    prefs = manager.reset(datetime.now(timezone.utc).isoformat())
    _audit_action(user, "os_preferences_reset", {}, success=True)
    return {
        "status": "success",
        "preferences": prefs.__dict__,
        "capabilities": manager.capabilities(),
        "message": "OS preferences reset.",
    }


@app.get("/api/os/safety/state")
async def os_safety_state(user=Depends(verify_token)):
    """Return recovery, safe-mode, checkpoint, and safety-gate state."""
    return _safety_state_payload()


@app.post("/api/os/safety/safe-mode")
async def os_safety_safe_mode(request: SafetyModeRequest, user=Depends(verify_token)):
    """Enable or disable safe mode."""
    result = _get_safety_manager().set_safe_mode(request.enabled, request.reason)
    _audit_action(user, "safety_safe_mode", {"enabled": request.enabled, "reason": request.reason}, result.success)
    return {
        **_safety_state_payload(),
        "message": result.message,
    }


@app.post("/api/os/safety/recovery-mode")
async def os_safety_recovery_mode(request: SafetyModeRequest, user=Depends(verify_token)):
    """Enable or disable recovery mode."""
    result = _get_safety_manager().set_recovery_mode(request.enabled, request.reason)
    _audit_action(user, "safety_recovery_mode", {"enabled": request.enabled, "reason": request.reason}, result.success)
    return {
        **_safety_state_payload(),
        "message": result.message,
    }


@app.post("/api/os/safety/checkpoint")
async def os_safety_checkpoint(request: SafetyCheckpointRequest, user=Depends(verify_token)):
    """Create a recovery checkpoint manifest."""
    result = _get_safety_manager().create_checkpoint(request.label, request.notes or "")
    _audit_action(user, "safety_checkpoint", {"label": request.label, "checkpoint": result.checkpoint.id if result.checkpoint else None}, result.success)
    return {
        **_safety_state_payload(),
        "message": result.message,
        "checkpoint": result.checkpoint.__dict__ if result.checkpoint else None,
    }


@app.get("/api/os/safety/checkpoints")
async def os_safety_checkpoints(limit: int = 10, user=Depends(verify_token)):
    """List recent recovery checkpoints."""
    checkpoints = _get_safety_manager().list_checkpoints(limit=max(1, min(limit, 50)))
    return {
        "status": "success",
        "checkpoints": [checkpoint.__dict__ for checkpoint in checkpoints],
        "count": len(checkpoints),
    }


@app.post("/api/os/safety/restore")
async def os_safety_restore(request: SafetyRestoreRequest, user=Depends(verify_token)):
    """Plan or restore files from a recovery checkpoint."""
    result = _get_safety_manager().restore_checkpoint(
        request.checkpoint_id,
        dry_run=request.dry_run,
        confirmed=request.confirmed,
    )
    _audit_action(
        user,
        "safety_restore",
        {
            "checkpoint_id": request.checkpoint_id,
            "dry_run": request.dry_run,
            "confirmed": request.confirmed,
            "restored": (result.data or {}).get("restored", []),
        },
        result.success,
    )
    return {
        **_safety_state_payload(),
        "success": result.success,
        "message": result.message,
        "data": result.data or {},
    }


@app.post("/api/os/safety/maintenance-command")
async def os_safety_maintenance_command(request: MaintenanceCommandRequest, user=Depends(verify_token)):
    """Run an allowlisted offline maintenance diagnostic command."""
    result = _get_safety_manager().run_maintenance_command(request.command, request.timeout_seconds)
    _audit_action(
        user,
        "safety_maintenance_command",
        {"command": request.command, "blocked": result.blocked, "returncode": result.returncode},
        result.success,
    )
    return {
        "success": result.success,
        "command": result.command,
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "blocked": result.blocked,
        "allowlist": _get_safety_manager().maintenance_allowlist(),
    }


@app.get("/api/os/audit/recent")
async def os_audit_recent(limit: int = 20, user=Depends(verify_token)):
    """Return recent audit entries for the current user."""
    assistant = _get_assistant()
    audit_logger = getattr(assistant, "persistence", {}).get("audit_logger") if assistant else None
    if not audit_logger:
        return {"status": "unavailable", "entries": [], "count": 0}
    entries = audit_logger.get_user_audit_log(user.get("user_id", "shrey_ceo"), limit=max(1, min(limit, 100)))
    return {"status": "success", "entries": entries, "count": len(entries)}


def _package_result_payload(result) -> Dict[str, Any]:
    return {
        "success": result.success,
        "action": result.action,
        "dry_run": result.dry_run,
        "message": result.message,
        "plan": {
            "action": result.plan.action,
            "package": result.plan.package,
            "command": result.plan.command,
            "provider": result.plan.provider,
            "requires_confirmation": result.plan.requires_confirmation,
            "blocked": result.plan.blocked,
            "reason": result.plan.reason,
        },
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": result.timestamp,
    }


@app.get("/api/os/packages/state")
async def os_packages_state(user=Depends(verify_token)):
    """Return package lifecycle provider and safety state."""
    return {
        "status": "success",
        "package_manager": _get_package_manager().provider_state(),
        "safety": _safety_state_payload().get("state"),
    }


@app.post("/api/os/packages/search")
async def os_packages_search(request: PackageSearchRequest, user=Depends(verify_token)):
    """Search packages through the detected package provider."""
    result = _get_package_manager().search(request.query)
    return _package_result_payload(result)


@app.get("/api/os/packages/installed")
async def os_packages_installed(user=Depends(verify_token)):
    """List installed packages through the detected package provider."""
    result = _get_package_manager().list_installed()
    return _package_result_payload(result)


@app.post("/api/os/packages/action")
async def os_packages_action(request: PackageActionRequest, user=Depends(verify_token)):
    """Plan or execute install/uninstall/update through safety gates."""
    result = _get_package_manager().execute(
        request.action,
        request.package,
        dry_run=request.dry_run,
        confirmed=request.confirmed,
        safety_state=_get_safety_manager().state(),
    )
    _audit_action(
        user,
        f"package_{request.action}",
        {
            "package": request.package,
            "dry_run": request.dry_run,
            "confirmed": request.confirmed,
            "provider": result.plan.provider,
            "blocked": result.plan.blocked,
        },
        result.success,
    )
    return _package_result_payload(result)


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


@app.get("/api/os/apps")
async def os_apps(user=Depends(verify_token)):
    """Return allowlisted launchable applications."""
    return {"status": "success", "apps": _allowed_apps_payload(), "count": len(APP_ALLOWLIST)}


@app.post("/api/os/apps/launch")
async def os_app_launch(request: AppLaunchRequest, user=Depends(verify_token)):
    """Plan or launch an allowlisted desktop application."""
    result = _launch_allowed_app(request.app, request.dry_run, request.confirmed)
    _audit_action(
        user,
        "app_launch",
        {"app": request.app, "dry_run": request.dry_run, "confirmed": request.confirmed},
        result.get("success", False),
    )
    return result


@app.get("/api/os/services")
async def os_services(user=Depends(verify_token)):
    """Return tracked services."""
    services = _get_service_manager().list_services()
    return {"services": services, "count": len(services)}


@app.post("/api/os/services/action")
async def os_services_action(request: ServiceActionRequest, user=Depends(verify_token)):
    """Plan or execute tracked service lifecycle actions."""
    result = _run_service_action(request)
    _audit_action(
        user,
        f"service_{request.action}",
        {
            "name": request.name,
            "directory": request.directory,
            "port": request.port,
            "dry_run": request.dry_run,
            "confirmed": request.confirmed,
        },
        result.get("success", False),
    )
    return result


@app.get("/api/os/control/health")
async def os_control_health(user=Depends(verify_token)):
    """Check the local privileged control broker without performing a mutation."""
    try:
        return await asyncio.to_thread(ControlBrokerClient().request, "broker.health")
    except ControlBrokerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/os/control/service")
async def os_control_service(request: SystemServiceActionRequest, user=Depends(verify_token)):
    """Inspect or restart an allowlisted system service through the root broker."""
    action = request.action.strip().lower()
    if action not in {"status", "restart"}:
        raise HTTPException(status_code=400, detail="Only status and restart are supported")
    if action == "restart" and request.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "action": "service.restart",
            "params": {"name": request.name},
            "requires_confirmation": True,
        }
    try:
        result = await asyncio.to_thread(
            ControlBrokerClient().request,
            f"service.{action}",
            {"name": request.name},
            confirmed=request.confirmed,
            reason=request.reason,
        )
    except ControlBrokerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _audit_action(
        user,
        f"control_service_{action}",
        {
            "name": request.name,
            "dry_run": request.dry_run,
            "confirmed": request.confirmed,
            "broker_ok": result.get("ok", False),
        },
        result.get("ok", False),
    )
    return result


@app.get("/api/os/devices")
async def os_devices(user=Depends(verify_token)):
    """Return a high signal hardware snapshot for the OS control layer."""
    return _get_device_manager().snapshot()


@app.post("/api/os/hardware/validate")
async def os_hardware_validate(request: HardwareValidationRequest, user=Depends(verify_token)):
    """Run Phase 4 hardware validation and persist a compatibility report."""
    report = _get_hardware_validation_manager().run_validation(
        label=request.label,
        notes=request.notes or "",
        save=request.save,
    )
    _audit_action(
        user,
        "hardware_validation",
        {
            "report_id": report.get("id"),
            "label": request.label,
            "overall_status": report.get("overall_status"),
            "score": report.get("score"),
            "saved": request.save,
        },
        True,
    )
    return {"status": "success", "report": report}


@app.get("/api/os/hardware/reports")
async def os_hardware_reports(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 4 hardware validation reports."""
    reports = _get_hardware_validation_manager().list_reports(limit=max(1, min(limit, 50)))
    return {"status": "success", "reports": reports, "count": len(reports)}


@app.get("/api/os/hardware/matrix")
async def os_hardware_matrix(limit: int = 20, user=Depends(verify_token)):
    """Return a compatibility matrix across saved target configurations."""
    matrix = _get_hardware_validation_manager().compatibility_matrix(limit=max(1, min(limit, 100)))
    return {"status": "success", "matrix": matrix}


@app.post("/api/os/hardware/stress-capture")
async def os_hardware_stress_capture(request: HardwareStressRequest, user=Depends(verify_token)):
    """Run a short Phase 4 hardware stress/thermal capture."""
    report = _get_hardware_stress_manager().run_capture(
        label=request.label,
        notes=request.notes or "",
        duration_seconds=request.duration_seconds,
        interval_seconds=request.interval_seconds,
        save=request.save,
    )
    _audit_action(
        user,
        "hardware_stress_capture",
        {
            "report_id": report.get("id"),
            "label": request.label,
            "duration_seconds": report.get("duration_seconds"),
            "overall_status": report.get("overall_status"),
            "saved": request.save,
        },
        True,
    )
    return {"status": "success", "report": report}


@app.get("/api/os/hardware/stress-reports")
async def os_hardware_stress_reports(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 4 hardware stress/thermal reports."""
    reports = _get_hardware_stress_manager().list_reports(limit=max(1, min(limit, 50)))
    return {"status": "success", "reports": reports, "count": len(reports)}


@app.post("/api/os/security/audit")
async def os_security_audit(request: SecurityAuditRequest, user=Depends(verify_token)):
    """Run a Phase 6 security hardening audit."""
    report = _get_security_audit_manager().run_audit(
        cors_origins=CORS_ORIGINS,
        session_tokens=SESSION_TOKENS,
        safety_state=_get_safety_manager().state(),
        save=request.save,
    )
    _audit_action(
        user,
        "security_audit",
        {
            "report_id": report.get("id"),
            "overall_status": report.get("overall_status"),
            "score": report.get("score"),
            "saved": request.save,
        },
        report.get("overall_status") != "fail",
    )
    return {"status": "success", "report": report}


@app.get("/api/os/security/audits")
async def os_security_audits(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 6 security hardening audits."""
    reports = _get_security_audit_manager().list_reports(limit=max(1, min(limit, 50)))
    return {"status": "success", "reports": reports, "count": len(reports)}


@app.post("/api/os/performance/baseline")
async def os_performance_baseline(request: PerformanceBaselineRequest, user=Depends(verify_token)):
    """Run a Phase 6 performance baseline and memory drift check."""
    report = _get_performance_baseline_manager().run_baseline(
        label=request.label,
        notes=request.notes or "",
        duration_seconds=request.duration_seconds,
        interval_seconds=request.interval_seconds,
        save=request.save,
    )
    _audit_action(
        user,
        "performance_baseline",
        {
            "report_id": report.get("id"),
            "label": request.label,
            "duration_seconds": report.get("duration_seconds"),
            "overall_status": report.get("overall_status"),
            "rss_growth_mb": report.get("summary", {}).get("rss_growth_mb"),
            "saved": request.save,
        },
        report.get("overall_status") != "fail",
    )
    return {"status": "success", "report": report}


@app.get("/api/os/performance/baselines")
async def os_performance_baselines(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 6 performance baseline reports."""
    reports = _get_performance_baseline_manager().list_reports(limit=max(1, min(limit, 50)))
    return {"status": "success", "reports": reports, "count": len(reports)}


@app.post("/api/os/failover/drill")
async def os_failover_drill(request: FailoverDrillRequest, user=Depends(verify_token)):
    """Run a Phase 6 non-mutating failover drill."""
    report = _get_failover_drill_manager().run_drill(
        label=request.label,
        notes=request.notes or "",
        save=request.save,
    )
    _audit_action(
        user,
        "failover_drill",
        {
            "report_id": report.get("id"),
            "label": request.label,
            "overall_status": report.get("overall_status"),
            "score": report.get("score"),
            "saved": request.save,
        },
        report.get("overall_status") != "fail",
    )
    return {"status": "success", "report": report}


@app.get("/api/os/failover/drills")
async def os_failover_drills(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 6 failover drill reports."""
    reports = _get_failover_drill_manager().list_reports(limit=max(1, min(limit, 50)))
    return {"status": "success", "reports": reports, "count": len(reports)}


@app.post("/api/os/release/evidence")
async def os_release_evidence(request: ReleaseEvidenceRequest, user=Depends(verify_token)):
    """Create a Phase 6 release-candidate evidence bundle."""
    bundle = _get_release_evidence_manager().create_bundle(
        label=request.label,
        notes=request.notes or "",
        save=request.save,
    )
    _audit_action(
        user,
        "release_evidence_bundle",
        {
            "bundle_id": bundle.get("id"),
            "label": request.label,
            "release_status": bundle.get("release_status"),
            "score": bundle.get("score"),
            "saved": request.save,
        },
        bundle.get("release_status") != "blocked",
    )
    return {"status": "success", "bundle": bundle}


@app.get("/api/os/release/evidence")
async def os_release_evidence_list(limit: int = 10, user=Depends(verify_token)):
    """List saved Phase 6 release evidence bundles."""
    bundles = _get_release_evidence_manager().list_bundles(limit=max(1, min(limit, 50)))
    return {"status": "success", "bundles": bundles, "count": len(bundles)}


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


class SystemVolumeRequest(BaseModel):
    level: int


class SystemBrightnessRequest(BaseModel):
    level: int


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


class VoiceTrainingRecordRequest(BaseModel):
    """Request model for voice training phrase capture."""
    phrase_id: str
    prompt: str
    transcript: str
    confidence: float = 0.75
    language: str = "en-US"
    duration_ms: Optional[int] = None


@app.get("/api/os/voice/state")
async def os_voice_state(user=Depends(verify_token)):
    """Get current voice system state."""
    try:
        manager = _get_voice_manager()
        state = manager.state()
        
        return {
            "status": "success",
            "state": {
                "mode": state.mode,
                "listening": state.is_listening,
                "wake_word_enabled": state.wake_word_enabled,
                "wake_word": "jarvis" if state.wake_word_enabled else None,
                "microphones": 1 if state.microphone_available else 0,
                "speakers": 1 if state.speaker_available else 0,
                "microphone_available": state.microphone_available,
                "speaker_available": state.speaker_available,
                "commands_processed": state.commands_processed,
                "average_confidence": round(state.average_confidence, 3),
                "last_command": {
                    "text": state.last_command.text if state.last_command else None,
                    "confidence": round(state.last_command.confidence, 3) if state.last_command else None,
                    "timestamp": state.last_command.recognized_at if state.last_command else None,
                } if state.last_command else None,
                "last_response": {
                    "text": state.last_response.text if state.last_response else None,
                    "status": state.last_response.status if state.last_response else None,
                    "timestamp": state.last_response.generated_at if state.last_response else None,
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
                    "timestamp": command.recognized_at,
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
                "timestamp": response.generated_at,
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


@app.get("/api/os/voice/training")
async def os_voice_training(user=Depends(verify_token)):
    """Return voice training prompts and current profile progress."""
    try:
        manager = _get_voice_manager()
        return manager.training_plan()
    except Exception as e:
        logger.error(f"Voice training state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/voice/training/record")
async def os_voice_training_record(request: VoiceTrainingRecordRequest, user=Depends(verify_token)):
    """Persist one voice training phrase sample."""
    try:
        manager = _get_voice_manager()
        payload = manager.record_training_phrase(
            phrase_id=request.phrase_id,
            prompt=request.prompt,
            transcript=request.transcript,
            confidence=request.confidence,
            language=request.language,
            duration_ms=request.duration_ms,
        )
        _audit_action(
            user,
            "voice_training_record",
            {
                "phrase_id": request.phrase_id,
                "confidence": request.confidence,
                "language": request.language,
            },
            success=True,
        )
        return payload
    except Exception as e:
        logger.error(f"Voice training record error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/os/voice/training/reset")
async def os_voice_training_reset(user=Depends(verify_token)):
    """Reset persisted voice training profile."""
    try:
        manager = _get_voice_manager()
        payload = manager.reset_training()
        _audit_action(user, "voice_training_reset", {}, success=True)
        return payload
    except Exception as e:
        logger.error(f"Voice training reset error: {e}")
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


@app.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket):
    """Stream voice analytics data over WebSocket."""
    token = websocket.query_params.get("token")
    if not token or token not in SESSION_TOKENS:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        while True:
            router = _get_voice_router()
            history = router.get_history(8)

            history_data = [
                {
                    "command": entry.command_text,
                    "response": entry.response_text,
                    "confidence": entry.confidence,
                    "status": entry.status.value,
                    "duration_ms": entry.duration_ms,
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in history
            ]

            history_mgr = router.history_manager
            perf_mgr = router.performance_monitor
            stats = history_mgr.get_stats()
            perf_stats = perf_mgr.get_stats("voice_command")

            payload = {
                "history": history_data,
                "stats": {
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
                    },
                },
                "context": router.get_session_summary(),
            }

            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("Voice analytics stream disconnected")
    except Exception as exc:
        logger.warning(f"Voice analytics stream error: {exc}")
        await websocket.close(code=1011)


# ── Gesture Recognition Endpoints ────────────────────────────────────────────


@app.get("/api/gesture/state")
async def gesture_state(user=Depends(verify_token)):
    """Return current gesture recognition state."""
    manager = _get_gesture_manager()
    return {"status": "success", **manager.state()}


@app.post("/api/gesture/start")
async def gesture_start(user=Depends(verify_token)):
    """Start a gesture recognition session."""
    manager = _get_gesture_manager()
    result = manager.start()
    _audit_action(user, "gesture_start", {"result": result.get("status")})
    return result


@app.post("/api/gesture/stop")
async def gesture_stop(user=Depends(verify_token)):
    """Stop the gesture recognition session."""
    manager = _get_gesture_manager()
    result = manager.stop()
    _audit_action(user, "gesture_stop", {"result": result.get("status")})
    return result


@app.get("/api/gesture/frame")
async def gesture_frame(user=Depends(verify_token)):
    """Return the latest annotated gesture frame as base64 JPEG."""
    manager = _get_gesture_manager()
    frame_b64 = manager.current_frame_base64()
    state = manager.state()
    return {
        "status": "success",
        "frame": frame_b64,
        "gesture": state.get("gesture"),
        "confidence": state.get("confidence"),
        "hand_count": state.get("hand_count"),
        "pointer_x": state.get("pointer_x"),
        "pointer_y": state.get("pointer_y"),
        "pinch_distance": state.get("pinch_distance"),
    }


@app.get("/api/gesture/events")
async def gesture_events(limit: int = 20, user=Depends(verify_token)):
    """Return recent gesture events."""
    manager = _get_gesture_manager()
    events = manager.recent_events(limit=max(1, min(limit, 50)))
    return {"status": "success", "events": events}


@app.get("/api/gesture/actions")
async def gesture_actions_get(user=Depends(verify_token)):
    """Return the current gesture→action mapping."""
    manager = _get_gesture_manager()
    return {"status": "success", "action_map": manager.get_action_map()}


@app.post("/api/gesture/actions")
async def gesture_actions_update(body: GestureActionMapUpdate, user=Depends(verify_token)):
    """Update a single gesture→action mapping."""
    manager = _get_gesture_manager()
    update = {
        body.gesture: {
            "action": body.action,
            "label": body.label,
            "description": body.description,
        }
    }
    result = manager.update_action_map(update)
    _audit_action(user, "gesture_action_update", {"gesture": body.gesture, "action": body.action})
    return {"status": "success", **result}


@app.post("/api/gesture/actions/reset")
async def gesture_actions_reset(user=Depends(verify_token)):
    """Reset gesture→action mapping to defaults."""
    manager = _get_gesture_manager()
    result = manager.reset_action_map()
    _audit_action(user, "gesture_action_reset")
    return {"status": "success", **result}


@app.get("/api/gesture/capabilities")
async def gesture_capabilities(user=Depends(verify_token)):
    """Return gesture system capabilities."""
    manager = _get_gesture_manager()
    return {"status": "success", **manager.capability_matrix()}


@app.websocket("/ws/gesture")
async def gesture_websocket(websocket: WebSocket):
    """Real-time gesture event + frame WebSocket stream."""
    await websocket.accept()
    manager = _get_gesture_manager()
    try:
        while True:
            state = manager.state()
            payload = {
                "gesture": state.get("gesture"),
                "confidence": state.get("confidence"),
                "hand_count": state.get("hand_count"),
                "active": state.get("active"),
                "pointer_x": state.get("pointer_x"),
                "pointer_y": state.get("pointer_y"),
                "pinch_distance": state.get("pinch_distance"),
                "frame": manager.current_frame_base64(),
                "timestamp": state.get("timestamp"),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.066)  # ~15 fps
    except WebSocketDisconnect:
        logger.info("Gesture WebSocket disconnected")
    except Exception as exc:
        logger.warning(f"Gesture WebSocket error: {exc}")
        await websocket.close(code=1011)


# ── System Control Endpoints ─────────────────────────────────────────────────


@app.get("/api/system/audio")
async def system_audio_get(user=Depends(verify_token)):
    """Return system audio status."""
    manager = _get_system_manager()
    return manager.get_volume()


@app.post("/api/system/audio")
async def system_audio_set(body: SystemVolumeRequest, user=Depends(verify_token)):
    """Set system audio volume."""
    manager = _get_system_manager()
    result = manager.set_volume(body.level)
    _audit_action(user, "system_volume_change", {"level": body.level})
    return result


@app.post("/api/system/audio/mute")
async def system_audio_mute(user=Depends(verify_token)):
    """Toggle system mute."""
    manager = _get_system_manager()
    result = manager.toggle_mute()
    _audit_action(user, "system_mute_toggle", {"muted": result.get("muted")})
    return result


@app.get("/api/system/display")
async def system_display_get(user=Depends(verify_token)):
    """Return system brightness status."""
    manager = _get_system_manager()
    return manager.get_brightness()


@app.post("/api/system/display")
async def system_display_set(body: SystemBrightnessRequest, user=Depends(verify_token)):
    """Set system brightness."""
    manager = _get_system_manager()
    result = manager.set_brightness(body.level)
    _audit_action(user, "system_brightness_change", {"level": body.level})
    return result


@app.get("/api/system/power")
async def system_power_get(user=Depends(verify_token)):
    """Return system power and battery status."""
    manager = _get_system_manager()
    return manager.get_power_status()


@app.get("/api/system/hardware")
async def system_hardware_get(user=Depends(verify_token)):
    """Return real-time hardware load (CPU/RAM/Disk)."""
    manager = _get_system_manager()
    return {"status": "success", "metrics": manager.get_system_load()}


@app.get("/api/system/capabilities")
async def system_capabilities(user=Depends(verify_token)):
    """Return what the system OS allows JARVIS to control."""
    manager = _get_system_manager()
    return {"status": "success", **manager.capability_matrix()}


# ── Intelligence (Phase 11) ────────────────────────────────────────────────
@app.get("/api/intelligence/insights")
async def get_insights(user=Depends(verify_token)):
    service = _get_proactive_service()
    return {"status": "success", "insights": service.get_insights()}

@app.get("/api/intelligence/memory")
async def search_memory(q: str, user=Depends(verify_token)):
    engine = _get_memory_engine()
    return {"status": "success", "results": engine.retrieve_context(q)}

@app.post("/api/intelligence/memory")
async def add_memory(req: MemoryEntry, user=Depends(verify_token)):
    engine = _get_memory_engine()
    entry = engine.add_episodic_memory(req.user, req.assistant, req.tags)
    _audit_action(user, "memory_add", {"id": entry["id"]})
    return {"status": "success", "entry": entry}


# ── Neural Macros ──────────────────────────────────────────────────────────

@app.post("/api/macros/create")
async def create_macro(req: MacroCreateRequest, user=Depends(verify_token)):
    """Create a new Neural Macro orchestration."""
    macro_data = {
        "user_id": user["user_id"],
        "name": req.name,
        "description": req.description,
        "steps": [step.dict() for step in req.steps],
        "trigger_phrase": req.trigger_phrase,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db[MACRO_COLLECTION].insert_one(macro_data)
    _audit_action(user, "macro_create", {"name": req.name})
    return {"status": "success", "macro_id": str(result.inserted_id)}

@app.get("/api/macros/list")
async def list_macros(user=Depends(verify_token)):
    """List all registered Neural Macros for the user."""
    macros = []
    async for doc in db[MACRO_COLLECTION].find({"user_id": user["user_id"]}):
        doc["id"] = str(doc.pop("_id"))
        macros.append(doc)
    return {"status": "success", "macros": macros}

@app.post("/api/macros/execute")
async def execute_macro(req: MacroExecuteRequest, user=Depends(verify_token)):
    """Execute a Neural Macro sequence."""
    from bson import ObjectId
    macro = await db[MACRO_COLLECTION].find_one({"_id": ObjectId(req.macro_id), "user_id": user["user_id"]})
    if not macro:
        raise HTTPException(status_code=404, detail="Macro not found")

    logger.info(f"Executing Macro: {macro['name']}")
    results = []

    for step in macro["steps"]:
        step_type = step["type"]
        value = step["value"]

        logger.info(f"Macro Step: {step_type} - {value}")

        try:
            if step_type == "command":
                # Process via ReActAgent / Assistant
                assistant = _get_assistant()
                resp = await assistant.process_query_async(value)
                results.append({"step": value, "status": "executed", "response": resp})

            elif step_type == "app":
                # Launch application
                _launch_allowed_app(value, dry_run=False, confirmed=True)
                results.append({"step": f"Launch {value}", "status": "launched"})

            elif step_type == "wait":
                # Sleep for specified seconds
                wait_time = int(value)
                await asyncio.sleep(wait_time)
                results.append({"step": f"Wait {wait_time}s", "status": "completed"})

        except Exception as e:
            logger.error(f"Macro step failed: {e}")
            results.append({"step": value, "status": "failed", "error": str(e)})

    _audit_action(user, "macro_execute", {"name": macro["name"]})
    return {"status": "success", "macro": macro["name"], "results": results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.environ.get("JARVIS_HOST", "0.0.0.0"),
        port=int(os.environ.get("JARVIS_BACKEND_PORT", "8001")),
    )
