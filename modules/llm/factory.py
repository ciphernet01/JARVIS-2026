"""
LLM factory for JARVIS.
Gemini is the active model.
"""

import logging
from importlib import import_module
from typing import Any

from core.config import ConfigManager

logger = logging.getLogger(__name__)

# Test hooks / patch targets; runtime imports are loaded dynamically.
GeminiManager = None
CompositeLLMManager = None


def create_llm_manager(config: Any = None) -> Any:
    """Create a Gemini-only LLM router."""
    cfg = config or ConfigManager()
    
    # If the user passed the full ConfigManager, extract the `llm` portion
    if hasattr(cfg, "llm"):
        llm_cfg = cfg.llm
    else:
        llm_cfg = cfg
        
    gemini_api_key = getattr(llm_cfg, "api_key", None)
    if not gemini_api_key and hasattr(cfg, "get_api_key"):
        gemini_api_key = cfg.get_api_key("gemini") or cfg.get_api_key("GEMINI")

    gemini_cls = GeminiManager
    router_cls = CompositeLLMManager

    if gemini_cls is None or router_cls is None:
        gemini_module = import_module("modules.llm.gemini")
        router_module = import_module("modules.llm.router")

        gemini_cls = gemini_cls or gemini_module.GeminiManager
        router_cls = router_cls or router_module.CompositeLLMManager

    primary = gemini_cls(
        api_key=gemini_api_key,
        model=getattr(llm_cfg, "model", "gemini-2.5-flash"),
        temperature=getattr(llm_cfg, "temperature", 0.2),
        top_p=getattr(llm_cfg, "top_p", 0.9),
        timeout_seconds=getattr(llm_cfg, "timeout_seconds", 60),
        system_prompt=getattr(llm_cfg, "system_prompt", None),
    )

    router = router_cls(primary=primary, fallback=None)
    logger.info("LLM router initialized with Gemini only")
    return router
