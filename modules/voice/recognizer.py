"""
Speech Recognition Module
Handles voice input and speech-to-text
"""

import logging
from typing import Optional

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False
    logger = logging.getLogger(__name__)
    logger.warning("speech_recognition not available")

logger = logging.getLogger(__name__)


class Recognizer:
    """High-level speech recognition interface"""

    def __init__(self, language: str = "en-US", timeout: int = 10):
        """
        Initialize speech recognizer

        Args:
            language: Language for recognition (e.g., 'en-US', 'hi-IN')
            timeout: Listening timeout in seconds
        """
        if not HAS_SR:
            raise ImportError("speech_recognition module not installed")

        self.recognizer = sr.Recognizer()
        self.language = language
        self.timeout = timeout
        self.is_listening = False

    def listen_once(self) -> Optional[str]:
        """
        Listen for speech and return transcribed text

        Returns:
            Transcribed text or None if no speech detected
        """
        if not HAS_SR:
            logger.error("speech_recognition not available")
            return None

        self.is_listening = True
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Listening...")
                audio = self.recognizer.listen(source, timeout=self.timeout, phrase_time_limit=15)

            # Try Google Speech Recognition
            text = self.recognizer.recognize_google(audio, language=self.language)
            logger.info(f"Recognized: {text}")
            return text

        except sr.UnknownValueError:
            logger.info("Silence or unrecognized audio.")
            return None
        except sr.WaitTimeoutError:
            logger.info("Listening timed out.")
            return None
        except sr.RequestError as e:
            logger.error(f"Could not request results from speech recognition service: {e}")
            return None
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
        finally:
            self.is_listening = False

    def listen_continuous(self, callback, stop_event=None):
        """
        Continuously listen for speech

        Args:
            callback: Function to call with recognized text
            stop_event: Event to stop listening
        """
        if not HAS_SR:
            logger.error("speech_recognition not available")
            return

        logger.info("Starting continuous listening...")
        while not (stop_event and stop_event.is_set()):
            text = self.listen_once()
            if text:
                callback(text)

    def set_language(self, language: str) -> None:
        """Set recognition language"""
        self.language = language
        logger.info(f"Language set to: {language}")

    def set_timeout(self, timeout: int) -> None:
        """Set listening timeout"""
        self.timeout = timeout
        logger.info(f"Timeout set to: {timeout} seconds")
