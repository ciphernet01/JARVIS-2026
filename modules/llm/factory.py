"""Provider-neutral LLM factory for local and remote A.S.T.R.A runtimes."""

import logging
from importlib import import_module
from typing import Any

from core.config import ConfigManager

logger = logging.getLogger(__name__)

# Test hooks / patch targets; runtime imports are loaded dynamically.
GeminiManager = None
CompositeLLMManager = None


def create_llm_manager(config: Any = None) -> Any:
    """Create an LLM router with local inference primary and optional Gemini fallback."""
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
        local_module = import_module("modules.llm.local_runtime")

        gemini_cls = gemini_cls or gemini_module.GeminiManager
        router_cls = router_cls or router_module.CompositeLLMManager
        local_cls = local_module.OpenAICompatibleManager
    else:
        local_cls = import_module("modules.llm.local_runtime").OpenAICompatibleManager

    # Decide primary based on configured provider and availability
    provider_pref = getattr(llm_cfg, "provider", None)

    # Construct candidates
    local_inst = local_cls(
        base_url=getattr(llm_cfg, "base_url", "http://localhost:11434/v1"),
        model=getattr(llm_cfg, "model", "qwen2.5-coder:7b"),
        provider=provider_pref or "local",
        api_key=getattr(llm_cfg, "api_key", "local") or "local",
        temperature=getattr(llm_cfg, "temperature", 0.2),
        top_p=getattr(llm_cfg, "top_p", 0.9),
        timeout_seconds=getattr(llm_cfg, "timeout_seconds", 60),
        system_prompt=getattr(llm_cfg, "system_prompt", None),
    )

    gemini_inst = gemini_cls(
        api_key=gemini_api_key,
        model=(
            getattr(llm_cfg, "model", "gemini-2.5-flash")
            if provider_pref == "gemini"
            else getattr(llm_cfg, "fallback_model", "gemini-2.5-flash")
        ),
        temperature=getattr(llm_cfg, "temperature", 0.2),
        top_p=getattr(llm_cfg, "top_p", 0.9),
        timeout_seconds=getattr(llm_cfg, "timeout_seconds", 60),
        system_prompt=getattr(llm_cfg, "system_prompt", None),
    )

    primary = local_inst
    fallback = gemini_inst

    if provider_pref == "gemini":
        try:
            if getattr(gemini_inst, "is_available", lambda: False)():
                primary = gemini_inst
                # When provider is explicitly Gemini and it's available, do not set a fallback
                fallback = None
        except Exception:
            # If availability check fails, fall back to defaults
            primary = local_inst

    router = router_cls(primary=primary, fallback=fallback)
    logger.info("LLM router initialized with primary=%s", type(primary).__name__)
    return router
