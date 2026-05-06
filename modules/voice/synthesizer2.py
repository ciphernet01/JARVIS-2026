"""
Text-to-Speech (TTS) Synthesizer Module
Handles voice output with multiple engine support
"""

import logging
from typing import Optional
from abc import ABC, abstractmethod
import queue
import threading
import pyttsx3

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """Base class for TTS engines"""

    @abstractmethod
    def speak(self, text: str, wait: bool = True) -> None:
        """Speak the given text"""
        pass

    @abstractmethod
    def set_voice(self, voice_id: str) -> None:
        """Set the voice"""
        pass

    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """Set speech rate (words per minute)"""
        pass

    @abstractmethod
    def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)"""
        pass


class PyTTSX3Engine(TTSEngine):
    """pyttsx3-based TTS engine (Windows native) using a single background thread"""

    def __init__(self):
        """Initialize PyTTSX3 engine"""
        self.message_queue = queue.Queue()
        self.is_running = True
        
        # We start the engine in a background thread to prevent SAPI COM errors
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()
        
        self._current_rate = 180
        self._current_volume = 1.0
        self._current_voice = None
        
        # Expose dummy voices list to support the API without needing SAPI up front on main thread
        self.available_voices = []

    def _tts_worker(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            engine = pyttsx3.init()
            
            # Load voices
            self.available_voices = engine.getProperty("voices")
            logger.info("Background PyTTSX3 worker initialized")
            
            while self.is_running:
                try:
                    task = self.message_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                    
                if task is None:
                    break
                    
                # Task format: (action, data, event)
                action, data, event = task
                
                try:
                    if action == "speak":
                        if self._current_voice:
                            engine.setProperty("voice", self._current_voice)
                        engine.setProperty("rate", self._current_rate)
                        engine.setProperty("volume", self._current_volume)
                        engine.say(data)
                        engine.runAndWait()
                    elif action == "set_voice":
                        self._current_voice = data
                    elif action == "set_rate":
                        self._current_rate = data
                    elif action == "set_volume":
                        self._current_volume = data
                except Exception as e:
                    logger.error(f"TTS Engine execution error: {e}")
                finally:
                    if event:
                        event.set()
                        
            pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"TTS Worker died: {e}")

    def get_voices(self) -> list:
        return [
            {
                "id": voice.id,
                "name": voice.name,
                "languages": getattr(voice, "languages", []),
            }
            for voice in self.available_voices
        ]

    def speak(self, text: str, wait: bool = True) -> None:
        if not text or not text.strip():
            return
        
        logger.debug(f"Speaking: {text[:50]}...")
        event = threading.Event() if wait else None
        self.message_queue.put(("speak", text, event))
        
        if wait:
            event.wait()

    def set_voice(self, voice_id: str) -> None:
        self.message_queue.put(("set_voice", voice_id, None))

    def set_rate(self, rate: int) -> None:
        rate = max(50, min(300, rate))
        self.message_queue.put(("set_rate", rate, None))

    def set_volume(self, volume: float) -> None:
        volume = max(0.0, min(1.0, volume))
        self.message_queue.put(("set_volume", volume, None))
        
    def close(self):
        self.is_running = False
        self.message_queue.put(None)


class Synthesizer:
    """High-level TTS interface"""

    def __init__(self, engine_type: str = "pyttsx3", voice_id: Optional[str] = None):
        self.engine_type = engine_type
        self.engine = self._create_engine(engine_type)
        self.is_speaking = False

        if voice_id:
            self.set_voice(voice_id)

    def _create_engine(self, engine_type: str) -> TTSEngine:
        if engine_type.lower() == "pyttsx3":
            return PyTTSX3Engine()
        else:
            logger.warning(f"Unknown engine type: {engine_type}, defaulting to pyttsx3")
            return PyTTSX3Engine()

    def speak(self, text: str, wait: bool = True) -> None:
        self.is_speaking = True
        try:
            self.engine.speak(text, wait=wait)
        finally:
            self.is_speaking = False

    def set_voice(self, voice_id: str) -> None:
        self.engine.set_voice(voice_id)

    def set_rate(self, rate: int) -> None:
        self.engine.set_rate(rate)

    def set_volume(self, volume: float) -> None:
        self.engine.set_volume(volume)

    def get_available_voices(self) -> list:
        if hasattr(self.engine, "get_voices"):
            return self.engine.get_voices()
        return []
