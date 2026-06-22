"""A.S.T.R.A core package with dependency-light lazy public imports."""

from .config import ConfigManager
from .exceptions import (
    JARVISException,
    ConfigurationError,
    VoiceError,
    SkillError,
    AuthenticationError,
    IntegrationError,
    PermissionError,
    AgentError,
)


def __getattr__(name):
    """Load cloud/agent components only when callers actually request them."""
    if name == "Assistant":
        from .assistant import Assistant

        return Assistant
    if name == "LLMRouter":
        from .llm_router import LLMRouter

        return LLMRouter
    if name == "ReActAgent":
        from .agent import ReActAgent

        return ReActAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ConfigManager",
    "Assistant",
    "LLMRouter",
    "ReActAgent",
    "JARVISException",
    "ConfigurationError",
    "VoiceError",
    "SkillError",
    "AuthenticationError",
    "IntegrationError",
    "PermissionError",
    "AgentError",
]
