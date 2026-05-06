"""
LLM Router
Routes calls to the active Gemini model.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CompositeLLMManager:
    """Gemini-first LLM router."""

    def __init__(self, primary: Any = None, fallback: Any = None):
        self.primary = primary
        self.fallback = fallback

    def is_available(self) -> bool:
        return bool((self.primary and self.primary.is_available()) or (self.fallback and self.fallback.is_available()))

    def _call_with_fallback(self, method_name: str, *args, **kwargs):
        last_error = None
        for candidate, label in ((self.primary, "primary"), (self.fallback, "fallback")):
            if not candidate:
                continue
            method = getattr(candidate, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(*args, **kwargs)
                if result not in (None, "", {}, []):
                    return result
            except Exception as exc:
                last_error = exc
                logger.warning(f"{label} LLM {method_name} failed: {exc}")
        if method_name == "decide_action":
            return {"type": "answer", "response": "", "confidence": 0.0, "error": str(last_error) if last_error else None}
        return ""

    def decide_action(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_with_fallback("decide_action", user_input, context)

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self._call_with_fallback("chat", prompt, context)

    def refine_response(self, user_input: str, tool_result: str, context: Dict[str, Any]) -> str:
        return self._call_with_fallback("refine_response", user_input, tool_result, context)

    def coding_assistance(self, prompt: str, repo_context: Optional[str] = None) -> str:
        return self._call_with_fallback("coding_assistance", prompt, repo_context)
