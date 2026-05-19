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
        """Continuous sliding window audio processing for wake word detection."""
        import speech_recognition as sr
        r = sr.Recognizer()

        # Audio constants for openwakeword (typically 16kHz, 1280 samples)
        CHUNK_SIZE = 1280

        try:
            with sr.Microphone(sample_rate=16000) as source:
                logger.info("Neural Shell always-listening mode engaged.")

                # Sliding window buffer
                while self.running:
                    # Capture precise chunk
                    audio = r.record(source, duration=CHUNK_SIZE/16000.0)
                    audio_data = np.frombuffer(audio.get_raw_data(), np.int16)

                    if len(audio_data) == 0:
                        continue

                    # Process chunk through the neural model
                    # openwakeword maintains internal state for the sliding window
                    self.model.predict(audio_data)

                    # Check scores for the target wake word
                    for mdl in self.model.prediction_buffer:
                        # Use a 0.6 threshold for high-fidelity detection in the shell
                        scores = list(self.model.prediction_buffer[mdl])
                        if scores and scores[-1] > 0.6:
                            logger.info(f"Neural Trigger: {mdl} detected")
                            if self.callback:
                                # Run callback in a separate thread to not block the listener
                                threading.Thread(target=self.callback, args=(mdl,), daemon=True).start()

        except Exception as e:
            logger.error(f"Wake word loop error: {e}")
            self.running = False
