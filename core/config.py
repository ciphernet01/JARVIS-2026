"""
Configuration management for JARVIS
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Voice settings configuration"""
    engine: str = "pyttsx3"  # pyttsx3, azure, google, elevenlabs
    voice_id: str = "0"
    speech_rate: int = 150
    volume: float = 1.0
    recognizer_language: str = "en-US"
    recognizer_timeout: int = 10


@dataclass
class SecurityConfig:
    """Security settings configuration"""
    enable_encryption: bool = True
    enable_authentication: bool = False  # Requires user setup
    enable_audit_logging: bool = True
    password_required: bool = False
    session_timeout_minutes: int = 30
    vault_path: str = ""  # Auto-set to ~/.jarvis/credentials.vault
    encryption_key_path: str = ""  # Auto-set to ~/.jarvis/encryption.key


@dataclass
class UIConfig:
    """UI settings configuration"""
    theme: str = "dark"
    always_on_top: bool = False
    start_minimized: bool = False
    show_transcription: bool = True
    show_animation: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    log_file: str = "jarvis.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class LLMConfig:
    """Local or remote LLM configuration"""
    enabled: bool = True
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    api_key: str = ""
    fallback_provider: str = "ollama"
    fallback_model: str = "llama3.1"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.2
    top_p: float = 0.9
    timeout_seconds: int = 60
    system_prompt: str = (
        "You are JARVIS: concise, highly capable, proactive, and helpful. "
        "Prefer direct answers, use available tools when needed, and keep responses short unless more detail is requested."
    )


class ConfigManager:
    """Central configuration manager"""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir or Path.home() / ".jarvis")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load environment variables from the project .env first, then fall back to the default search.
        project_env = Path(__file__).resolve().parents[1] / ".env"
        if project_env.exists():
            load_dotenv(project_env, override=False)
        load_dotenv(override=False)

        # Initialize configurations
        self.voice = VoiceConfig()
        self.security = SecurityConfig()
        self.ui = UIConfig()
        self.logging_cfg = LoggingConfig()
        self.llm = LLMConfig()

        self.custom_config: Dict[str, Any] = {}

        self._load_env_overrides()

        # Load from configuration files if they exist
        self._load_configs()

    def _load_env_overrides(self) -> None:
        """Override config from environment variables when present."""
        enabled_value = os.getenv("LLM_ENABLED") or os.getenv("GEMINI_ENABLED") or os.getenv("OLLAMA_ENABLED")
        if enabled_value is not None:
            self.llm.enabled = enabled_value.lower() in {"1", "true", "yes", "on"}

        self.llm.provider = os.getenv("LLM_PROVIDER", self.llm.provider)
        self.llm.model = os.getenv("GEMINI_MODEL", self.llm.model)
        self.llm.api_key = os.getenv("GEMINI_API_KEY", self.llm.api_key)
        self.llm.fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", self.llm.fallback_provider)
        self.llm.fallback_model = os.getenv("OLLAMA_MODEL", self.llm.fallback_model)
        self.llm.base_url = os.getenv("OLLAMA_BASE_URL", self.llm.base_url)

        temperature = os.getenv("GEMINI_TEMPERATURE") or os.getenv("LLM_TEMPERATURE") or os.getenv("OLLAMA_TEMPERATURE")
        if temperature is not None:
            try:
                self.llm.temperature = float(temperature)
            except ValueError:
                logger.warning(f"Invalid OLLAMA_TEMPERATURE value: {temperature}")

        top_p = os.getenv("GEMINI_TOP_P") or os.getenv("LLM_TOP_P") or os.getenv("OLLAMA_TOP_P")
        if top_p is not None:
            try:
                self.llm.top_p = float(top_p)
            except ValueError:
                logger.warning(f"Invalid OLLAMA_TOP_P value: {top_p}")

        timeout_seconds = os.getenv("GEMINI_TIMEOUT_SECONDS") or os.getenv("LLM_TIMEOUT_SECONDS") or os.getenv("OLLAMA_TIMEOUT_SECONDS")
        if timeout_seconds is not None:
            try:
                self.llm.timeout_seconds = int(timeout_seconds)
            except ValueError:
                logger.warning(f"Invalid OLLAMA_TIMEOUT_SECONDS value: {timeout_seconds}")

    def _load_configs(self) -> None:
        """Load configuration from files"""
        config_file = self.config_dir / "jarvis.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    self._apply_config(data)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")

    def _apply_config(self, data: Dict[str, Any]) -> None:
        """Apply configuration from dictionary"""
        if "voice" in data:
            for key, value in data["voice"].items():
                if hasattr(self.voice, key):
                    setattr(self.voice, key, value)

        if "security" in data:
            for key, value in data["security"].items():
                if hasattr(self.security, key):
                    setattr(self.security, key, value)

        if "ui" in data:
            for key, value in data["ui"].items():
                if hasattr(self.ui, key):
                    setattr(self.ui, key, value)

        if "llm" in data:
            for key, value in data["llm"].items():
                if hasattr(self.llm, key):
                    setattr(self.llm, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.custom_config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.custom_config[key] = value

    def save(self) -> None:
        """Save configuration to file"""
        config_file = self.config_dir / "jarvis.json"
        try:
            config_data = {
                "voice": asdict(self.voice),
                "security": asdict(self.security),
                "ui": asdict(self.ui),
                "llm": asdict(self.llm),
                "custom": self.custom_config,
            }
            with open(config_file, "w") as f:
                json.dump(config_data, f, indent=2)
            logger.info(f"Saved configuration to {config_file}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key from environment variables"""
        env_key = f"{service.upper()}_API_KEY"
        return os.getenv(env_key)
