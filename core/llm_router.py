"""
LLM Router for JARVIS
3-tier fallback: Gemini → Groq → Ollama
Async, typed, with call logging and quota fallback.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from openai import AsyncOpenAI, APIError, RateLimitError

from core.config import ConfigManager
from core.exceptions import ConfigurationError, IntegrationError

logger = logging.getLogger(__name__)


@dataclass
class LLMCallLog:
    """Log entry for a single LLM call."""

    model: str
    provider: str
    latency_ms: float
    tokens_used: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMResponse:
    """Structured response from any LLM provider."""

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    provider: str = ""
    call_log: Optional[LLMCallLog] = None


class GeminiClient:
    """Async Gemini client using google-genai (native async API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 30,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are JARVIS, an advanced AI assistant created by Sypher Industries. "
            "Your CEO is Shrey. Be concise, expert-level, and proactive. "
            "Prefer direct answers and use available tools when needed."
        )
        self._client: Optional[genai.Client] = None

    def _ensure_client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                raise ConfigurationError("Gemini API key not configured")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _to_gemini_contents(
        self, messages: List[Dict[str, str]]
    ) -> List[types.Content]:
        """Convert OpenAI-style messages to Gemini content list."""
        contents: List[types.Content] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            gemini_role = "model" if role in ("assistant", "system") else "user"
            contents.append(
                types.Content(role=gemini_role, parts=[types.Part(text=text)])
            )
        return contents

    def _to_gemini_tools(self, tools: List[Dict[str, Any]]) -> List[types.Tool]:
        """Convert OpenAI-style tool schemas to Gemini tool format."""
        declarations: List[types.FunctionDeclaration] = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
            else:
                func = tool
            declarations.append(
                types.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=func.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract function calls from Gemini response."""
        calls: List[Dict[str, Any]] = []
        try:
            for candidate in response.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        args = {}
                        if hasattr(fc, "args"):
                            raw_args = fc.args
                            if hasattr(raw_args, "items"):
                                args = dict(raw_args)
                            else:
                                args = {"value": str(raw_args)}
                        calls.append({"name": fc.name, "arguments": args})
        except Exception as exc:
            logger.debug(f"No tool calls extracted: {exc}")
        return calls

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        start = time.time()
        try:
            gemini_contents = self._to_gemini_contents(messages)
            gemini_tools = self._to_gemini_tools(tools) if tools else None

            config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                system_instruction=self.system_prompt,
                tools=gemini_tools,
            )

            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model_name,
                    contents=gemini_contents,
                    config=config,
                ),
                timeout=self.timeout_seconds,
            )

            latency = (time.time() - start) * 1000
            content = (getattr(response, "text", None) or "").strip()
            tool_calls = self._extract_tool_calls(response)
            tokens = len(str(gemini_contents).split()) + len(content.split())

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model_used=self.model_name,
                provider="gemini",
                call_log=LLMCallLog(
                    model=self.model_name,
                    provider="gemini",
                    latency_ms=latency,
                    tokens_used=tokens,
                    success=True,
                ),
            )
        except asyncio.TimeoutError:
            logger.warning("Gemini call timed out")
            raise IntegrationError("Gemini request timed out")
        except Exception as exc:
            err_msg = str(exc)
            logger.warning(f"Gemini chat failed: {err_msg}")
            if "429" in err_msg or "quota" in err_msg.lower() or "rate limit" in err_msg.lower():
                raise RateLimitError(
                    message=err_msg,
                    response=None,
                    body=None,
                )
            raise IntegrationError(f"Gemini error: {err_msg}")

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError("Gemini embedding not implemented in JARVIS router")


class GroqClient:
    """Async Groq client using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 30,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are JARVIS. Be concise, expert-level, and proactive."
        )
        self._client: Optional[AsyncOpenAI] = None

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ConfigurationError("GROQ_API_KEY not set")
            self._client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        start = time.time()
        try:
            payload: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await client.chat.completions.create(**payload)

            latency = (time.time() - start) * 1000
            choice = response.choices[0]
            message = choice.message
            content = (message.content or "").strip()
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )

            tokens = response.usage.total_tokens if response.usage else None

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model_used=self.model_name,
                provider="groq",
                call_log=LLMCallLog(
                    model=self.model_name,
                    provider="groq",
                    latency_ms=latency,
                    tokens_used=tokens,
                    success=True,
                ),
            )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            err_msg = str(exc)
            logger.warning(f"Groq chat failed: {err_msg}")
            raise

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError("Groq embedding not available")


class XAIClient:
    """Async xAI (Grok) client using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "grok-beta",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 30,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are JARVIS. Be concise, expert-level, and proactive."
        )
        self._client: Optional[AsyncOpenAI] = None

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ConfigurationError("XAI_API_KEY not set")
            self._client = AsyncOpenAI(
                base_url="https://api.x.ai/v1",
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        start = time.time()
        try:
            payload: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await client.chat.completions.create(**payload)

            latency = (time.time() - start) * 1000
            choice = response.choices[0]
            message = choice.message
            content = (message.content or "").strip()
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )

            tokens = response.usage.total_tokens if response.usage else None

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model_used=self.model_name,
                provider="xai",
                call_log=LLMCallLog(
                    model=self.model_name,
                    provider="xai",
                    latency_ms=latency,
                    tokens_used=tokens,
                    success=True,
                ),
            )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            err_msg = str(exc)
            logger.warning(f"xAI chat failed: {err_msg}")
            raise

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError("xAI embedding not available")


class OllamaClient:
    """Async Ollama client using OpenAI-compatible /v1 endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5-coder:7b",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 30,
        system_prompt: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are JARVIS. Be concise, expert-level, and proactive."
        )
        self._client: Optional[AsyncOpenAI] = None

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key="ollama",
                timeout=self.timeout_seconds,
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        start = time.time()
        try:
            payload: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await client.chat.completions.create(**payload)

            latency = (time.time() - start) * 1000
            choice = response.choices[0]
            message = choice.message
            content = (message.content or "").strip()
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )

            tokens = response.usage.total_tokens if response.usage else None

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model_used=self.model_name,
                provider="ollama",
                call_log=LLMCallLog(
                    model=self.model_name,
                    provider="ollama",
                    latency_ms=latency,
                    tokens_used=tokens,
                    success=True,
                ),
            )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            err_msg = str(exc)
            logger.warning(f"Ollama chat failed: {err_msg}")
            raise

    async def embed(self, text: str) -> List[float]:
        client = self._ensure_client()
        try:
            response = await client.embeddings.create(
                model="nomic-embed-text",
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning(f"Ollama embedding failed: {exc}")
            raise


class LLMRouter:
    """
    Routes LLM calls across Gemini, Groq, and Ollama with automatic fallback.

    Routing logic (per copilot-instructions.md):
      - voice / real-time       → Groq (speed)
      - code / build tasks      → Gemini 2.5 Pro (quality)
      - quick rewrite / summary → Gemini 2.0 Flash
      - offline / quota hit     → Ollama qwen2.5-coder
      - embeddings              → Ollama nomic-embed-text
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        cfg = config or ConfigManager()
        llm_cfg = cfg.llm if hasattr(cfg, "llm") else cfg

        gemini_api_key = getattr(llm_cfg, "api_key", None) or cfg.get_api_key("gemini") or os.getenv("GEMINI_API_KEY")
        groq_api_key = cfg.get_api_key("groq") or os.getenv("GROQ_API_KEY")
        xai_api_key = cfg.get_api_key("xai") or os.getenv("XAI_API_KEY")
        ollama_base = getattr(llm_cfg, "base_url", "http://localhost:11434/v1")
        temperature = getattr(llm_cfg, "temperature", 0.2)
        top_p = getattr(llm_cfg, "top_p", 0.9)
        timeout = getattr(llm_cfg, "timeout_seconds", 30)
        system_prompt = getattr(llm_cfg, "system_prompt", None)

        self.gemini_pro = GeminiClient(
            api_key=gemini_api_key,
            model="gemini-2.5-pro",
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.gemini_flash = GeminiClient(
            api_key=gemini_api_key,
            model="gemini-2.0-flash",
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.groq = GroqClient(
            api_key=groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.xai = XAIClient(
            api_key=xai_api_key,
            model="grok-beta",
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.ollama_coder = OllamaClient(
            base_url=ollama_base,
            model=os.getenv("OLLAMA_MODEL", "gemma4:latest"),
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.ollama_general = OllamaClient(
            base_url=ollama_base,
            model=os.getenv("OLLAMA_MODEL", "gemma4:latest"),
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout,
            system_prompt=system_prompt,
        )
        self.call_history: List[LLMCallLog] = []

    def _log_call(self, call_log: LLMCallLog) -> None:
        self.call_history.append(call_log)
        logger.info(
            f"LLM call [{call_log.provider}/{call_log.model}] latency={call_log.latency_ms:.0f}ms "
            f"tokens={call_log.tokens_used} success={call_log.success}"
        )

    async def _try_providers(
        self,
        providers: List[tuple],
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Try providers in order, falling back on RateLimitError or IntegrationError."""
        last_error: Optional[Exception] = None
        for client, label in providers:
            try:
                response = await client.chat(messages, tools=tools)
                self._log_call(response.call_log)
                return response
            except (RateLimitError, IntegrationError) as exc:
                last_error = exc
                logger.warning(f"{label} rate-limited / unavailable, trying next tier: {exc}")
                continue
            except Exception as exc:
                last_error = exc
                logger.warning(f"{label} failed unexpectedly, trying next tier: {exc}")
                continue

        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(error_msg)
        self._log_call(
            LLMCallLog(
                model="none",
                provider="none",
                latency_ms=0.0,
                success=False,
                error=error_msg,
            )
        )
        raise IntegrationError(error_msg)

    async def build_task(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Code generation / build tasks → Gemini 2.5 Pro, fallback xAI/Grok → Groq → Ollama."""
        providers = [
            (self.gemini_pro, "Gemini Pro"),
            (self.xai, "xAI Grok"),
            (self.groq, "Groq"),
            (self.ollama_coder, "Ollama qwen2.5-coder"),
        ]
        return await self._try_providers(providers, messages, tools)

    async def quick_task(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Quick rewrites / summaries → Gemini 2.0 Flash, fallback xAI/Grok → Groq → Ollama."""
        providers = [
            (self.gemini_flash, "Gemini Flash"),
            (self.xai, "xAI Grok"),
            (self.groq, "Groq"),
            (self.ollama_general, "Ollama mistral"),
        ]
        return await self._try_providers(providers, messages, tools)

    async def voice_task(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Voice / real-time response → Groq (speed priority), fallback xAI/Grok → Gemini Flash → Ollama."""
        providers = [
            (self.groq, "Groq"),
            (self.xai, "xAI Grok"),
            (self.gemini_flash, "Gemini Flash"),
            (self.ollama_general, "Ollama mistral"),
        ]
        return await self._try_providers(providers, messages, tools)

    async def offline_task(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Offline / quota exceeded → Ollama, fallback to Gemini Flash."""
        providers = [
            (self.ollama_coder, "Ollama qwen2.5-coder"),
            (self.ollama_general, "Ollama mistral"),
            (self.gemini_flash, "Gemini Flash"),
        ]
        return await self._try_providers(providers, messages, tools)

    async def embed(self, text: str) -> List[float]:
        """Embeddings → Ollama nomic-embed-text."""
        try:
            return await self.ollama_general.embed(text)
        except Exception as exc:
            logger.error(f"Embedding failed: {exc}")
            raise IntegrationError(f"Embedding failed: {exc}")
