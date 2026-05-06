"""
JARVIS Neural Interface - FastAPI Backend
Advanced AI Assistant with Gemini integration
"""

import os
import sys
import logging
import platform
import uuid
import psutil
import requests as http_requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_START_TIME = datetime.now(timezone.utc)

# MongoDB
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Emergent LLM
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

# Session management
SESSION_TOKENS = {}

app = FastAPI(title="JARVIS Neural Interface API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    method: str = "biometric"

class CommandRequest(BaseModel):
    command: str
    session_id: Optional[str] = None

class CodeRequest(BaseModel):
    prompt: str
    repo_context: Optional[str] = None
    language: Optional[str] = "python"


# ── Auth ─────────────────────────────────────────────────────────────────────
def verify_token(request: Request):
    token = request.headers.get("X-JARVIS-TOKEN")
    if not token or token not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized. Security protocol active.")
    return SESSION_TOKENS[token]


# ── LLM Chat Helper ─────────────────────────────────────────────────────────
async def jarvis_chat(prompt: str, system_message: str = None, session_id: str = "default") -> str:
    """Chat with Gemini via emergentintegrations"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        if not system_message:
            system_message = (
                "You are JARVIS, an advanced AI assistant inspired by the Iron Man movies. "
                "You are deeply knowledgeable, witty with dry British humor, proactive, and fiercely loyal. "
                "You address the user as 'Sir' and provide concise, expert-level responses. "
                "You have expertise in software development, system administration, and general knowledge. "
                "Keep responses focused and actionable."
            )

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"jarvis-{session_id}",
            system_message=system_message,
        )
        chat.with_model("gemini", "gemini-2.5-flash")

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        return f"I'm experiencing a temporary neural link disruption, Sir. Error: {str(e)}"


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

    return await jarvis_chat(full_prompt, system_message=system_message, session_id="dev-mode")


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
    """Biometric/session login - generates a session token"""
    token = str(uuid.uuid4())
    user_data = {
        "user_id": "shrey_ceo",
        "user_name": "Sir",
        "login_time": datetime.now(timezone.utc).isoformat(),
        "method": req.method,
    }
    SESSION_TOKENS[token] = user_data

    # Log to MongoDB
    await db.sessions.insert_one({
        "token": token,
        "user_id": "shrey_ceo",
        "login_time": datetime.now(timezone.utc).isoformat(),
        "method": req.method,
    })

    return {
        "success": True,
        "token": token,
        "message": "Biometric verification complete. Welcome back, Sir.",
        "user": {"name": "Sir", "id": "shrey_ceo"},
    }


@app.post("/api/command")
async def process_command(req: CommandRequest, user=Depends(verify_token)):
    """Process a command through JARVIS AI"""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="No command provided")

    session_id = req.session_id or "main"
    response = await jarvis_chat(command, session_id=session_id)

    # Save to conversation history
    await db.conversations.insert_one({
        "user_id": user["user_id"],
        "command": command,
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
    })

    return {
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/code/assist")
async def code_assist(req: CodeRequest, user=Depends(verify_token)):
    """Developer coding assistance"""
    response = await jarvis_code_assist(req.prompt, req.repo_context, req.language)

    await db.code_sessions.insert_one({
        "user_id": user["user_id"],
        "prompt": req.prompt,
        "response": response,
        "language": req.language,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

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
    """Get conversation history"""
    cursor = db.conversations.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit)

    history = await cursor.to_list(length=limit)
    history.reverse()
    return {"history": history}


@app.get("/api/status")
async def system_status(user=Depends(verify_token)):
    """Get JARVIS system status"""
    conv_count = await db.conversations.count_documents({})
    return {
        "status": "online",
        "llm_provider": "gemini-2.5-flash",
        "llm_available": bool(EMERGENT_LLM_KEY),
        "ollama_configured": bool(OLLAMA_BASE_URL),
        "conversation_count": conv_count,
        "platform": f"{platform.system()} {platform.release()}",
        "uptime_seconds": int((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
        "skills": [
            "chat", "code_assist", "system_metrics", "weather",
            "file_management", "developer_mode"
        ],
    }


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
    }
