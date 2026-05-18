"""Service layer for JARVIS OS handling."""

from .device_manager import DeviceManager
from .manager import ServiceManager, ServiceRecord
from .audio_manager import AudioManager
from .camera_manager import CameraManager
from .power_manager import PowerManager
from .network_manager import NetworkManager
from .voice_manager import VoiceManager, VoiceCommand, VoiceResponse, VoiceState
from .safety_manager import SafetyManager, SafetyState, SafetyCheckpoint, SafetyActionResult, MaintenanceCommandResult, SafetyGateDecision, SafetyGate
from .package_manager import PackageManager, PackageProvider, PackagePlan, PackageActionResult
from .hardware_validation_manager import HardwareValidationManager, HardwareValidationCheck, HardwareValidationReport
from .hardware_stress_manager import HardwareStressManager, HardwareStressSample, HardwareStressReport
from .preferences_manager import OSPreferencesManager, OSPreferences
from .security_audit_manager import SecurityAuditManager, SecurityAuditCheck, SecurityAuditReport
from .performance_baseline_manager import PerformanceBaselineManager, PerformanceSample, PerformanceBaselineReport
from .failover_drill_manager import FailoverDrillManager, FailoverDrillCheck, FailoverDrillReport
from .release_evidence_manager import ReleaseEvidenceManager, ReleaseEvidenceItem, ReleaseEvidenceBundle
from .release_manifest_manager import ReleaseManifestManager, ReleaseFile, ReleaseManifest
from .release_update_manager import ReleaseUpdateManager, UpdateAction

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
    "SafetyManager",
    "SafetyState",
    "SafetyCheckpoint",
    "SafetyActionResult",
    "MaintenanceCommandResult",
    "SafetyGateDecision",
    "SafetyGate",
    "PackageManager",
    "PackageProvider",
    "PackagePlan",
    "PackageActionResult",
    "HardwareValidationManager",
    "HardwareValidationCheck",
    "HardwareValidationReport",
    "HardwareStressManager",
    "HardwareStressSample",
    "HardwareStressReport",
    "OSPreferencesManager",
    "OSPreferences",
    "SecurityAuditManager",
    "SecurityAuditCheck",
    "SecurityAuditReport",
    "PerformanceBaselineManager",
    "PerformanceSample",
    "PerformanceBaselineReport",
    "FailoverDrillManager",
    "FailoverDrillCheck",
    "FailoverDrillReport",
    "ReleaseEvidenceManager",
    "ReleaseEvidenceItem",
    "ReleaseEvidenceBundle",
    "ReleaseManifestManager",
    "ReleaseFile",
    "ReleaseManifest",
    "ReleaseUpdateManager",
    "UpdateAction",
    "AIConversationEngine",
    "ConversationMemory",
    "IntentExtractor",
    "SkillExecutor",
    "get_conversation_engine",
]
