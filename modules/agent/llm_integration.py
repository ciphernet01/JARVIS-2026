"""
Phase 2: LLM Integration Layer

Unified interface for different LLM backends:
- OpenAI (GPT-4, GPT-3.5)
- Ollama (Local LLMs)
- Google Gemini
- Anthropic Claude (future)

This bridges AIConversationEngine with language models.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, AsyncIterator
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    CLAUDE = "claude"


@dataclass
class LLMConfig:
    """Configuration for LLM backend."""
    provider: LLMProvider
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 500
    timeout: int = 30


@dataclass
class LLMResponse:
    """Unified response from LLM."""
    content: str
    model: str
    tokens_used: int
    provider: LLMProvider


class LLMBase(ABC):
    """Abstract base for LLM implementations."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model_name = config.model_name
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    @abstractmethod
    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate text response."""
        pass

    @abstractmethod
    async def generate_full(self, prompt: str, context: str = "") -> LLMResponse:
        """Generate with full metadata."""
        pass

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        context: str = ""
    ) -> AsyncIterator[str]:
        """Stream text response chunk by chunk."""
        pass


class OpenAILLM(LLMBase):
    """OpenAI GPT integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            logger.warning("[OpenAI] No API key configured")

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            logger.error("[OpenAI] openai package not installed")
            self.client = None

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate response from OpenAI."""
        if not self.client:
            return "OpenAI client not available"

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are JARVIS, a helpful OS assistant."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.config.timeout
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"[OpenAI] Generation error: {e}")
            return f"Error: {str(e)}"

    async def generate_full(self, prompt: str, context: str = "") -> LLMResponse:
        """Generate with full metadata."""
        content = await self.generate(prompt, context)

        return LLMResponse(
            content=content,
            model=self.model_name,
            tokens_used=0,  # Would need to extract from response
            provider=LLMProvider.OPENAI
        )

    async def stream_generate(
        self,
        prompt: str,
        context: str = ""
    ) -> AsyncIterator[str]:
        """Stream response from OpenAI."""
        if not self.client:
            yield "OpenAI client not available"
            return

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are JARVIS, a helpful OS assistant."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                timeout=self.config.timeout
            )

            async for chunk in stream:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"[OpenAI] Stream error: {e}")
            yield f"Error: {str(e)}"


class OllamaLLM(LLMBase):
    """Local Ollama LLM integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")

        try:
            import httpx
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=config.timeout)
        except ImportError:
            logger.error("[Ollama] httpx package not installed")
            self.client = None

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate response from Ollama."""
        if not self.client:
            return "Ollama client not available"

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            response = await self.client.post(
                "/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": self.temperature,
                }
            )

            data = response.json()
            return data.get("response", "No response from Ollama")

        except Exception as e:
            logger.error(f"[Ollama] Generation error: {e}")
            return f"Error: {str(e)}"

    async def generate_full(self, prompt: str, context: str = "") -> LLMResponse:
        """Generate with full metadata."""
        content = await self.generate(prompt, context)

        return LLMResponse(
            content=content,
            model=self.model_name,
            tokens_used=0,
            provider=LLMProvider.OLLAMA
        )

    async def stream_generate(
        self,
        prompt: str,
        context: str = ""
    ) -> AsyncIterator[str]:
        """Stream response from Ollama."""
        if not self.client:
            yield "Ollama client not available"
            return

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            response = await self.client.post(
                "/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": True,
                    "temperature": self.temperature,
                }
            )

            async for line in response.aiter_lines():
                import json
                if line:
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk

        except Exception as e:
            logger.error(f"[Ollama] Stream error: {e}")
            yield f"Error: {str(e)}"


class GeminiLLM(LLMBase):
    """Google Gemini integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            logger.warning("[Gemini] No API key configured")

        try:
            import google.genai as genai
            self.client = genai
            if hasattr(self.client, "configure"):
                self.client.configure(api_key=self.api_key)
        except (ImportError, ValueError, AttributeError) as e:
            logger.error(f"[Gemini] Initialization error: {e}")
            self.client = None

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate response from Gemini."""
        if not self.client:
            return "Gemini client not available"

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            model = self.client.GenerativeModel(self.model_name)
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                }
            )

            return response.text

        except Exception as e:
            logger.error(f"[Gemini] Generation error: {e}")
            return f"Error: {str(e)}"

    async def generate_full(self, prompt: str, context: str = "") -> LLMResponse:
        """Generate with full metadata."""
        content = await self.generate(prompt, context)

        return LLMResponse(
            content=content,
            model=self.model_name,
            tokens_used=0,
            provider=LLMProvider.GEMINI
        )

    async def stream_generate(
        self,
        prompt: str,
        context: str = ""
    ) -> AsyncIterator[str]:
        """Stream response from Gemini."""
        if not self.client:
            yield "Gemini client not available"
            return

        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            model = self.client.GenerativeModel(self.model_name)
            response = model.generate_content(
                full_prompt,
                stream=True,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                }
            )

            for chunk in response:
                if hasattr(chunk, 'text'):
                    yield chunk.text

        except Exception as e:
            logger.error(f"[Gemini] Stream error: {e}")
            yield f"Error: {str(e)}"


class LLMFactory:
    """Factory for creating LLM instances."""

    _providers = {
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.OLLAMA: OllamaLLM,
        LLMProvider.GEMINI: GeminiLLM,
    }

    @classmethod
    def create(cls, config: LLMConfig) -> LLMBase:
        """Create LLM instance based on provider."""
        if config.provider not in cls._providers:
            raise ValueError(f"Unknown provider: {config.provider}")

        provider_class = cls._providers[config.provider]
        return provider_class(config)

    @classmethod
    def register(cls, provider: LLMProvider, impl_class: type) -> None:
        """Register custom LLM implementation."""
        cls._providers[provider] = impl_class


class LLMRouter:
    """
    Routes between multiple LLM backends with fallback support.
    Useful for:
    - Trying fast local Ollama first, then OpenAI if offline
    - Load balancing across multiple providers
    - Cost optimization
    """

    def __init__(self, configs: list[LLMConfig]):
        """
        Initialize router with multiple configurations.
        
        Args:
            configs: List of LLMConfig in priority order (first is primary)
        """
        self.configs = configs
        self.llms = [LLMFactory.create(config) for config in configs]
        self.current_index = 0

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate with automatic fallback."""
        for i, llm in enumerate(self.llms):
            try:
                logger.debug(f"[Router] Trying provider: {self.configs[i].provider.value}")
                response = await llm.generate(prompt, context)

                if response and not response.startswith("Error"):
                    self.current_index = i  # Remember working provider
                    return response

            except Exception as e:
                logger.warning(f"[Router] Provider failed: {self.configs[i].provider.value}: {e}")
                continue

        # All providers failed
        return "All LLM providers unavailable"

    async def generate_full(self, prompt: str, context: str = "") -> LLMResponse:
        """Generate with full metadata and fallback."""
        for i, llm in enumerate(self.llms):
            try:
                response = await llm.generate_full(prompt, context)
                self.current_index = i
                return response
            except Exception as e:
                logger.warning(f"[Router] Provider failed: {e}")
                continue

        return LLMResponse(
            content="All providers failed",
            model="unknown",
            tokens_used=0,
            provider=LLMProvider.OLLAMA
        )

    async def stream_generate(
        self,
        prompt: str,
        context: str = ""
    ) -> AsyncIterator[str]:
        """Stream with auto-fallback."""
        for i, llm in enumerate(self.llms):
            try:
                async for chunk in llm.stream_generate(prompt, context):
                    yield chunk
                self.current_index = i
                return
            except Exception as e:
                logger.warning(f"[Router] Provider failed: {e}")
                continue

        yield "All providers failed"

    def get_current_provider(self) -> LLMProvider:
        """Get currently active provider."""
        return self.configs[self.current_index].provider


def create_default_llm() -> Optional[LLMBase]:
    """
    Create default LLM with fallback chain:
    1. Local Ollama (no API costs)
    2. OpenAI (if key available)
    3. Gemini (if key available)
    """
    configs = []

    # Try local Ollama first
    configs.append(
        LLMConfig(
            provider=LLMProvider.OLLAMA,
            model_name="mistral",
            base_url="http://localhost:11434"
        )
    )

    # Add OpenAI if key available
    if os.getenv("OPENAI_API_KEY"):
        configs.append(
            LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="gpt-3.5-turbo"
            )
        )

    # Add Gemini if key available
    if os.getenv("GOOGLE_API_KEY"):
        configs.append(
            LLMConfig(
                provider=LLMProvider.GEMINI,
                api_key=os.getenv("GOOGLE_API_KEY"),
                model_name="gemini-pro"
            )
        )

    if not configs:
        logger.warning("[LLM] No LLM providers configured")
        return None

    if len(configs) == 1:
        return LLMFactory.create(configs[0])

    return LLMRouter(configs)
