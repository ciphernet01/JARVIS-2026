"""
Tests for core.llm_router
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm_router import LLMResponse, LLMCallLog
from core.exceptions import IntegrationError


class DummyClient:
    """Fake LLM client for routing tests."""

    def __init__(self, name: str, provider: str, fail: bool = False):
        self.name = name
        self.provider = provider
        self.fail = fail
        self.chat = AsyncMock(side_effect=self._chat)

    async def _chat(self, messages, tools=None):
        if self.fail:
            raise IntegrationError("quota exceeded")
        return LLMResponse(
            content=f"{self.name} response",
            tool_calls=[],
            model_used=self.name,
            provider=self.provider,
            call_log=LLMCallLog(
                model=self.name, provider=self.provider, latency_ms=100.0, success=True
            ),
        )


@pytest.mark.asyncio
async def test_try_providers_falls_back_on_failure():
    from core.llm_router import LLMRouter

    router = LLMRouter.__new__(LLMRouter)
    router.call_history = []

    # All fail
    bad = DummyClient("bad", "gemini", fail=True)
    router._log_call = lambda log: router.call_history.append(log)
    with pytest.raises(IntegrationError):
        await router._try_providers(
            [(bad, "bad")], messages=[{"role": "user", "content": "hi"}]
        )


@pytest.mark.asyncio
async def test_try_providers_succeeds_on_first():
    from core.llm_router import LLMRouter

    router = LLMRouter.__new__(LLMRouter)
    router.call_history = []
    router._log_call = lambda log: router.call_history.append(log)

    good = DummyClient("good", "gemini", fail=False)
    result = await router._try_providers(
        [(good, "good")], messages=[{"role": "user", "content": "hi"}]
    )
    assert result.provider == "gemini"
    assert result.content == "good response"
    assert len(router.call_history) == 1


@pytest.mark.asyncio
async def test_try_providers_falls_back_to_second():
    from core.llm_router import LLMRouter

    router = LLMRouter.__new__(LLMRouter)
    router.call_history = []
    router._log_call = lambda log: router.call_history.append(log)

    bad = DummyClient("bad", "gemini", fail=True)
    good = DummyClient("good", "groq", fail=False)
    result = await router._try_providers(
        [(bad, "bad"), (good, "good")],
        messages=[{"role": "user", "content": "hi"}],
    )
    assert result.provider == "groq"
    assert result.content == "good response"
