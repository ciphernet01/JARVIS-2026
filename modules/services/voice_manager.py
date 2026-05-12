"""
VoiceManager: Handles speech-to-text, text-to-speech, wake word detection, and voice processing.
Central hub for all voice interactions in JARVIS OS.
"""

import logging
import os
import sys
import threading
import json
import time
import subprocess
from dataclasses import dataclass
from typing import Optional, Callable, List
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional voice libraries
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logger.warning("speech_recognition not available, STT will be limited")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.warning("pyttsx3 not available, TTS will use fallback")


class VoiceMode(Enum):
    """Voice processing modes."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class ConfidenceLevel(Enum):
    """Confidence levels for voice recognition."""
    LOW = "low"  # < 0.6
    MEDIUM = "medium"  # 0.6-0.8
    HIGH = "high"  # > 0.8


@dataclass(frozen=True)
class VoiceCommand:
    """Immutable voice command recognition result."""
    text: str
    confidence: float
    language: str
    recognized_at: str  # ISO timestamp
    duration_ms: int
    source: str  # "microphone", "file", "api"


@dataclass(frozen=True)
class VoiceResponse:
    """Immutable voice response."""
    text: str
    audio_path: Optional[str]  # Path to generated audio file
    duration_ms: int
    status: str  # "success", "error"
    generated_at: str  # ISO timestamp


@dataclass(frozen=True)
class VoiceState:
    """Immutable snapshot of voice system state."""
    mode: str  # idle, listening, processing, speaking, error
    is_listening: bool
    wake_word_enabled: bool
    last_command: Optional[VoiceCommand]
    last_response: Optional[VoiceResponse]
    microphone_available: bool
    speaker_available: bool
    commands_processed: int
    average_confidence: float


class VoiceManager:
    """
    Central voice processing system for JARVIS OS.
    Handles STT, TTS, wake word detection, and voice command routing.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._mode = VoiceMode.IDLE
        self._is_listening = False
        self._wake_word_enabled = False
        self._recognizer = None
        self._tts_engine = None
        self._last_command = None
        self._last_response = None
        self._commands_processed = 0
        self._confidence_scores = []
        self._command_callbacks: List[Callable] = []
        self._lock = threading.Lock()

        self._initialize_engines()
        VoiceManager._initialized = True

    def _initialize_engines(self):
        """Initialize speech recognition and TTS engines."""
        try:
            if SPEECH_RECOGNITION_AVAILABLE:
                self._recognizer = sr.Recognizer()
                self._recognizer.energy_threshold = 4000
                logger.info("Speech recognition engine initialized")
            else:
                logger.warning("Speech recognition unavailable, will use fallback")
        except Exception as e:
            logger.error(f"Failed to initialize recognizer: {e}")

        try:
            if PYTTSX3_AVAILABLE:
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", 150)  # Slower for clarity
                self._tts_engine.setProperty("volume", 0.9)
                logger.info("TTS engine initialized")
            else:
                logger.warning("pyttsx3 unavailable, will use system TTS")
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")

    def state(self) -> VoiceState:
        """Get current voice system state."""
        with self._lock:
            avg_confidence = (
                sum(self._confidence_scores) / len(self._confidence_scores)
                if self._confidence_scores
                else 0.0
            )

            return VoiceState(
                mode=self._mode.value,
                is_listening=self._is_listening,
                wake_word_enabled=self._wake_word_enabled,
                last_command=self._last_command,
                last_response=self._last_response,
                microphone_available=self._check_microphone(),
                speaker_available=self._check_speaker(),
                commands_processed=self._commands_processed,
                average_confidence=avg_confidence,
            )

    def listen_for_command(
        self, timeout_seconds: float = 10.0, language: str = "en-US"
    ) -> Optional[VoiceCommand]:
        """
        Listen for voice command from microphone.

        Args:
            timeout_seconds: How long to listen for command
            language: Language/locale for recognition

        Returns:
            VoiceCommand if recognized, None if timeout or error
        """
        if not self._recognizer:
            logger.warning("Recognizer not available")
            return None

        with self._lock:
            self._mode = VoiceMode.LISTENING
            self._is_listening = True

        try:
            mic = sr.Microphone()
            with mic as source:
                # Adjust for ambient noise
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

                audio = self._recognizer.listen(source, timeout=timeout_seconds)

            # Process audio
            with self._lock:
                self._mode = VoiceMode.PROCESSING

            return self._process_audio(audio, language)

        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            self._mode = VoiceMode.ERROR
            return None
        except sr.RequestError as e:
            logger.error(f"Recognition service error: {e}")
            self._mode = VoiceMode.ERROR
            return None
        except Exception as e:
            logger.error(f"Error during listening: {e}")
            self._mode = VoiceMode.ERROR
            return None
        finally:
            with self._lock:
                self._is_listening = False
                if self._mode != VoiceMode.ERROR:
                    self._mode = VoiceMode.IDLE

    def _process_audio(self, audio, language: str) -> Optional[VoiceCommand]:
        """Process audio and convert to text."""
        try:
            # Try Google STT first
            text = self._recognizer.recognize_google(audio, language=language)

            # Calculate confidence (Google doesn't return confidence, so use 0.85 as default)
            confidence = 0.85

            command = VoiceCommand(
                text=text,
                confidence=confidence,
                language=language,
                recognized_at=datetime.utcnow().isoformat(),
                duration_ms=int(len(audio.frame_data) / audio.sample_rate * 1000),
                source="microphone",
            )

            with self._lock:
                self._last_command = command
                self._commands_processed += 1
                self._confidence_scores.append(confidence)
                if len(self._confidence_scores) > 100:  # Keep last 100
                    self._confidence_scores.pop(0)

            logger.info(f"Recognized command: {text} (confidence: {confidence})")
            return command

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return None

    def speak_response(self, text: str) -> VoiceResponse:
        """
        Convert text to speech and play it.

        Args:
            text: Text to speak

        Returns:
            VoiceResponse with status and audio details
        """
        with self._lock:
            self._mode = VoiceMode.SPEAKING

        start_time = time.time()

        try:
            if PYTTSX3_AVAILABLE and self._tts_engine:
                # Use pyttsx3 for TTS
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            else:
                # Fallback to espeak-ng
                self._use_espeak(text)

            duration_ms = int((time.time() - start_time) * 1000)

            response = VoiceResponse(
                text=text,
                audio_path=None,  # Could save to file if needed
                duration_ms=duration_ms,
                status="success",
                generated_at=datetime.utcnow().isoformat(),
            )

            with self._lock:
                self._last_response = response
                self._mode = VoiceMode.IDLE

            logger.info(f"Spoke response: {text[:50]}...")
            return response

        except Exception as e:
            logger.error(f"TTS error: {e}")
            with self._lock:
                self._mode = VoiceMode.ERROR

            return VoiceResponse(
                text=text,
                audio_path=None,
                duration_ms=0,
                status="error",
                generated_at=datetime.utcnow().isoformat(),
            )

    def _trim_confidence_scores(self) -> None:
        """Trim confidence scores to keep only the last 100."""
        with self._lock:
            if len(self._confidence_scores) > 100:
                self._confidence_scores = self._confidence_scores[-100:]

    def _use_espeak(self, text: str):
        """Fallback TTS using espeak-ng system command."""
        try:
            subprocess.run(
                ["espeak-ng", "-v", "en", "--", text],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except FileNotFoundError:
            logger.warning("espeak-ng not found, audio playback skipped")
        except Exception as e:
            logger.warning(f"espeak-ng error: {e}")

    def enable_wake_word(self, wake_word: str = "jarvis"):
        """
        Enable wake word detection.

        Args:
            wake_word: Word to listen for (e.g., "jarvis")
        """
        with self._lock:
            self._wake_word_enabled = True
        logger.info(f"Wake word detection enabled for: {wake_word}")

    def disable_wake_word(self):
        """Disable wake word detection."""
        with self._lock:
            self._wake_word_enabled = False
        logger.info("Wake word detection disabled")

    def register_command_callback(self, callback: Callable[[VoiceCommand], None]):
        """
        Register callback for when commands are recognized.

        Args:
            callback: Function to call with VoiceCommand
        """
        with self._lock:
            self._command_callbacks.append(callback)
        logger.debug(f"Registered voice command callback: {callback.__name__}")

    def process_command(self, command: VoiceCommand) -> dict:
        """
        Process a recognized voice command.

        Args:
            command: VoiceCommand to process

        Returns:
            dict with processing result
        """
        with self._lock:
            callbacks = self._command_callbacks.copy()

        result = {
            "command": command.text,
            "confidence": command.confidence,
            "callbacks_executed": 0,
        }

        for callback in callbacks:
            try:
                callback(command)
                result["callbacks_executed"] += 1
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return result

    def _check_microphone(self) -> bool:
        """Check if microphone is available."""
        try:
            if SPEECH_RECOGNITION_AVAILABLE:
                mic = sr.Microphone()
                with mic:
                    pass
                return True
        except Exception:
            pass
        return False

    def _check_speaker(self) -> bool:
        """Check if speaker is available."""
        try:
            # Try to list audio devices
            import pyaudio
            p = pyaudio.PyAudio()
            devices = p.get_device_count()
            p.terminate()
            return devices > 0
        except Exception:
            return False

    def capability_matrix(self) -> dict:
        """Get voice capabilities."""
        return {
            "stt_available": SPEECH_RECOGNITION_AVAILABLE,
            "tts_available": PYTTSX3_AVAILABLE,
            "microphone_available": self._check_microphone(),
            "speaker_available": self._check_speaker(),
            "wake_word_capable": True,
            "supported_languages": ["en-US", "es-ES", "fr-FR", "de-DE"],
        }
