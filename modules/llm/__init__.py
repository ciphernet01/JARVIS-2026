"""
LLM Module
Gemini-first local and remote LLM integration for JARVIS.
"""

from .gemini import GeminiManager
from .ollama import OllamaManager
from .router import CompositeLLMManager
from .factory import create_llm_manager
from .local_runtime import LocalRuntimeCapabilities, OpenAICompatibleManager

__all__ = [
    "GeminiManager",
    "OllamaManager",
    "CompositeLLMManager",
    "LocalRuntimeCapabilities",
    "OpenAICompatibleManager",
    "create_llm_manager",
]
