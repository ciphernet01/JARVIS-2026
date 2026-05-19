"""
Whisper-based local speech recognition for JARVIS.
"""

import logging
import os
import tempfile
import threading
from typing import Optional

import whisper
import torch
import numpy as np

logger = logging.getLogger(__name__)

class WhisperRecognizer:
    """Local STT using OpenAI Whisper."""

    _model = None
    _lock = threading.Lock()

    def __init__(self, model_name: str = "base", device: Optional[str] = None):
        """
        Initialize Whisper recognizer.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            device: 'cuda' or 'cpu'. Defaults to cuda if available.
        """
        self.model_name = model_name
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._ensure_model_loaded()
        logger.info(f"WhisperRecognizer initialized with model '{model_name}' on {self.device}")

    def _ensure_model_loaded(self):
        """Lazy load the Whisper model."""
        if WhisperRecognizer._model is None:
            with WhisperRecognizer._lock:
                if WhisperRecognizer._model is None:
                    logger.info(f"Loading Whisper model '{self.model_name}'...")
                    WhisperRecognizer._model = whisper.load_model(self.model_name, device=self.device)

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """
        Transcribe raw audio data.

        Args:
            audio_data: Numpy array of audio samples
            sample_rate: Audio sample rate

        Returns:
            Transcribed text
        """
        if WhisperRecognizer._model is None:
            return None

        try:
            # 1. Ensure float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0

            # 2. Resample to 16kHz if necessary
            if sample_rate != 16000:
                import scipy.signal
                num_samples = int(len(audio_data) * 16000 / sample_rate)
                audio_data = scipy.signal.resample(audio_data, num_samples)

            # Whisper expects 16k mono float32
            result = WhisperRecognizer._model.transcribe(audio_data, fp16=(self.device == "cuda"))
            text = result.get("text", "").strip()
            return text
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None

    def transcribe_file(self, file_path: str) -> Optional[str]:
        """Transcribe an audio file."""
        if WhisperRecognizer._model is None:
            return None

        try:
            result = WhisperRecognizer._model.transcribe(file_path, fp16=(self.device == "cuda"))
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Whisper file transcription error: {e}")
            return None
