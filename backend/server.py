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
import psutil
import numpy as np
import requests as http_requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import cv2

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


# ── Models ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    method: str = "biometric"
    image: Optional[str] = None  # Base64 webcam frame

class CommandRequest(BaseModel):
    command: str
    session_id: Optional[str] = None

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


# ── LLM Chat Helper ─────────────────────────────────────────────────────────
async def jarvis_chat(prompt: str, system_message: str = None, session_id: str = "default") -> str:
    """Chat with Gemini via emergentintegrations"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        if not system_message:
            system_message = (
                "You are JARVIS, an advanced AI assistant created by Sypher Industries. "
                "Your creator and CEO is Sir. You are deeply knowledgeable, witty with dry British humor, "
                "proactive, and fiercely loyal. You address the user as 'Sir' and provide concise, "
                "expert-level responses. You have expertise in software development, system administration, "
                "AI/ML engineering, and general knowledge. Keep responses focused and actionable."
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
    """Biometric face verification login - checks against imagedata/ folder and enrolled faces"""
    face_detected = False
    face_confidence = 0.0
    face_box = None  # {x, y, w, h} for frontend to draw rectangle
    verification_method = req.method

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

    await db.sessions.insert_one({
        "token": token,
        "user_id": "shrey_ceo",
        "login_time": datetime.now(timezone.utc).isoformat(),
        "method": verification_method,
        "face_detected": face_detected,
    })

    message = "Biometric verification complete. Welcome back, Sir."
    if face_detected:
        message = f"Face recognized (confidence: {face_confidence:.0%}). Welcome back, Sir."

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
    action_count = await db.vscode_actions.count_documents({})
    return {
        "status": "connected",
        "provider": "gemini-2.5-flash",
        "capabilities": ["complete", "explain", "fix", "refactor", "generate", "chat"],
        "total_actions": action_count,
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
