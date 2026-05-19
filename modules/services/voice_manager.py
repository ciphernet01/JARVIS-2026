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
    from modules.voice.whisper_recognizer import WhisperRecognizer
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("WhisperRecognizer not available, local STT disabled")

try:
    from modules.voice.wake_word import WakeWordDetector
    WAKE_WORD_AVAILABLE = True
except ImportError:
    WAKE_WORD_AVAILABLE = False
    logger.warning("WakeWordDetector not available")

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


TRAINING_PROMPTS = [
    "Jarvis, open the system dashboard",
    "Jarvis, show my recovery checkpoints",
    "Jarvis, lower the volume to twenty percent",
    "Jarvis, scan available networks",
    "Jarvis, start safe mode",
    "Jarvis, what is the hardware status",
]


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
        self._whisper = None
        self._wake_detector = None
        self._tts_engine = None
        self._last_command = None
        self._last_response = None
        self._commands_processed = 0
        self._confidence_scores = []
        self._command_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._training_path = (
            Path(os.environ.get("JARVIS_VOICE_TRAINING_PATH"))
            if os.environ.get("JARVIS_VOICE_TRAINING_PATH")
            else Path(__file__).resolve().parents[2] / "memory" / "voice" / "training_profile.json"
        )

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
            if WHISPER_AVAILABLE:
                # Load small model for balance between speed and accuracy
                self._whisper = WhisperRecognizer(model_name="base")
                logger.info("Whisper STT engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Whisper: {e}")

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
            text = ""
            confidence = 0.0

            # Try Local Whisper first for "Market Ready" zero-delay feel
            if self._whisper:
                import numpy as np
                # Convert audio to numpy array for Whisper
                audio_data = np.frombuffer(audio.get_raw_data(), np.int16).flatten().astype(np.float32) / 32768.0
                text = self._whisper.transcribe(audio_data)
                confidence = 0.9  # Whisper doesn't easily expose word-level confidence here
                logger.info(f"Whisper recognized: {text}")

            # Fallback to Google if Whisper fails or is unavailable
            if not text and SPEECH_RECOGNITION_AVAILABLE:
                text = self._recognizer.recognize_google(audio, language=language)
                confidence = 0.85
                logger.info(f"Google recognized (fallback): {text}")

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

    def _on_wake_word(self, word):
        """Internal callback for wake word detection."""
        logger.info(f"System triggered by wake word: {word}")
        # In a real shell, this would trigger the 'Listen' UI state
        # For now, we just log it and potentially fire specific callbacks
        self.listen_for_command()

    def enable_wake_word(self, wake_word: str = "jarvis"):
        """
        Enable wake word detection.

        Args:
            wake_word: Word to listen for (e.g., "jarvis")
        """
        with self._lock:
            if WAKE_WORD_AVAILABLE and not self._wake_detector:
                self._wake_detector = WakeWordDetector(wake_word, callback=self._on_wake_word)
                self._wake_detector.start()
            self._wake_word_enabled = True
        logger.info(f"Wake word detection enabled for: {wake_word}")

    def disable_wake_word(self):
        """Disable wake word detection."""
        with self._lock:
            if self._wake_detector:
                self._wake_detector.stop()
                self._wake_detector = None
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

    def _default_training_profile(self) -> dict:
        return {
            "status": "not_started",
            "language": "en-US",
            "started_at": None,
            "updated_at": None,
            "completed_at": None,
            "average_confidence": 0.0,
            "completion_ratio": 0.0,
            "samples": [],
        }

    def _load_training_profile(self) -> dict:
        try:
            if self._training_path.exists():
                with self._training_path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    return {**self._default_training_profile(), **loaded}
        except Exception as exc:
            logger.warning(f"Failed to load voice training profile: {exc}")
        return self._default_training_profile()

    def _save_training_profile(self, profile: dict) -> dict:
        self._training_path.parent.mkdir(parents=True, exist_ok=True)
        with self._training_path.open("w", encoding="utf-8") as handle:
            json.dump(profile, handle, indent=2, sort_keys=True)
        return profile

    def _score_phrase(self, prompt: str, transcript: str, confidence: float) -> float:
        expected = {token for token in re_tokenize(prompt) if token}
        actual = {token for token in re_tokenize(transcript) if token}
        overlap = len(expected & actual) / max(len(expected), 1)
        return round(max(0.0, min(1.0, (overlap * 0.6) + (confidence * 0.4))), 3)

    def training_plan(self) -> dict:
        """Return voice training prompts and current profile progress."""
        with self._lock:
            profile = self._load_training_profile()

        completed_ids = {sample.get("phrase_id") for sample in profile.get("samples", [])}
        prompts = [
            {
                "id": f"phrase_{index + 1}",
                "text": text,
                "completed": f"phrase_{index + 1}" in completed_ids,
            }
            for index, text in enumerate(TRAINING_PROMPTS)
        ]
        return {
            "status": "success",
            "profile": profile,
            "prompts": prompts,
            "minimum_completion_ratio": 0.75,
            "minimum_confidence": 0.6,
        }

    def record_training_phrase(
        self,
        phrase_id: str,
        prompt: str,
        transcript: str,
        confidence: float,
        language: str = "en-US",
        duration_ms: Optional[int] = None,
    ) -> dict:
        """Persist a voice-training sample and recompute readiness."""
        now = datetime.utcnow().isoformat()
        confidence = max(0.0, min(1.0, float(confidence)))
        sample = {
            "phrase_id": phrase_id,
            "prompt": prompt,
            "transcript": transcript.strip(),
            "confidence": confidence,
            "match_score": self._score_phrase(prompt, transcript, confidence),
            "language": language,
            "duration_ms": duration_ms,
            "recorded_at": now,
        }

        with self._lock:
            profile = self._load_training_profile()
            samples = [item for item in profile.get("samples", []) if item.get("phrase_id") != phrase_id]
            samples.append(sample)
            samples.sort(key=lambda item: item.get("phrase_id", ""))
            average = sum(item.get("match_score", 0.0) for item in samples) / max(len(samples), 1)
            completion_ratio = min(1.0, len({item.get("phrase_id") for item in samples}) / len(TRAINING_PROMPTS))
            ready = completion_ratio >= 0.75 and average >= 0.6
            profile.update({
                "status": "ready" if ready else "in_progress",
                "language": language,
                "started_at": profile.get("started_at") or now,
                "updated_at": now,
                "completed_at": now if ready else None,
                "average_confidence": round(average, 3),
                "completion_ratio": round(completion_ratio, 3),
                "samples": samples,
            })
            self._save_training_profile(profile)

        return self.training_plan()

    def reset_training(self) -> dict:
        """Reset persisted voice training state."""
        with self._lock:
            profile = self._save_training_profile(self._default_training_profile())
        return {
            "status": "success",
            "profile": profile,
            "prompts": self.training_plan()["prompts"],
        }


def re_tokenize(value: str) -> List[str]:
    """Normalize a voice phrase into comparable tokens without regex globals."""
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in value)
    return cleaned.split()
