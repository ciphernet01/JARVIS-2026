"""
Always-listening wake word detector for JARVIS OS.
Uses openwakeword for local, efficient keyword spotting.
"""

import logging
import threading
import time
import numpy as np
try:
    import openwakeword
    from openwakeword.model import Model
    HAS_OPENWAKEWORD = True
except ImportError:
    HAS_OPENWAKEWORD = False

logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(self, wake_word="jarvis", callback=None):
        self.wake_word = wake_word
        self.callback = callback
        self.model = None
        self.running = False
        self._thread = None

        if HAS_OPENWAKEWORD:
            try:
                # Initialize with specific model if available, else default
                self.model = Model(wakeword_models=[wake_word])
                logger.info(f"WakeWordDetector initialized for: {wake_word}")
            except Exception as e:
                logger.error(f"Failed to initialize openwakeword model: {e}")
        else:
            logger.warning("openwakeword not installed, wake word disabled")

    def start(self):
        if not self.model:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word listening started")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Wake word listening stopped")

    def _listen_loop(self):
        # This is a simplified loop. In production, this would interface with
        # PyAudio to get real-time chunks.
        import speech_recognition as sr
        r = sr.Recognizer()

        try:
            with sr.Microphone() as source:
                while self.running:
                    # Capture short chunks for wake word detection
                    audio = r.record(source, duration=1)
                    audio_data = np.frombuffer(audio.get_raw_data(), np.int16)

                    # Process chunk
                    prediction = self.model.predict(audio_data)

                    for mdl in prediction:
                        if prediction[mdl] > 0.5:
                            logger.info(f"Wake word detected: {mdl}")
                            if self.callback:
                                self.callback(mdl)

        except Exception as e:
            logger.error(f"Wake word loop error: {e}")
            self.running = False
