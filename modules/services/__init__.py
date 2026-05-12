"""Service layer for JARVIS OS handling."""

from .device_manager import DeviceManager
from .manager import ServiceManager, ServiceRecord
from .audio_manager import AudioManager
from .camera_manager import CameraManager
from .power_manager import PowerManager
from .network_manager import NetworkManager
from .voice_manager import VoiceManager, VoiceCommand, VoiceResponse, VoiceState

# Phase 2: AI Conversation Engine
try:
    from modules.agent.conversation_engine import (
        AIConversationEngine,
        ConversationMemory,
        IntentExtractor,
        SkillExecutor,
        get_conversation_engine,
    )
except (ImportError, SystemError):
    # Fallback if agent module not available
    pass

__all__ = [
    "DeviceManager",
    "ServiceManager",
    "ServiceRecord",
    "AudioManager",
    "CameraManager",
    "PowerManager",
    "NetworkManager",
    "VoiceManager",
    "VoiceCommand",
    "VoiceResponse",
    "VoiceState",
    "AIConversationEngine",
    "ConversationMemory",
    "IntentExtractor",
    "SkillExecutor",
    "get_conversation_engine",
]