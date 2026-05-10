"""
Tests for core.agent (ReAct loop)
Uses a mock LLM that returns scripted tool call sequences.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.agent import ReActAgent, AgentResult, ToolResult
from core.llm_router import LLMResponse, LLMCallLog


class MockLLMRouter:
    """Fake router that returns scripted responses."""

    def __init__(self, script):
        self.script = script  # list of LLMResponse
        self.idx = 0
        self.build_task = AsyncMock(side_effect=self._next)

    async def _next(self, messages, tools=None):
        resp = self.script[self.idx]
        self.idx = (self.idx + 1) % len(self.script)
        return resp


@pytest.fixture
def mock_tool():
    def _tool(name: str, **kwargs):
        return {"success": True, "output": f"ran {name}", "error": None}
    return _tool


@pytest.mark.asyncio
async def test_agent_returns_final_answer_without_tools():
    router = MockLLMRouter([
        LLMResponse(
            content="The answer is 42.",
            tool_calls=[],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
    ])
    agent = ReActAgent(llm_router=router, tools={})
    result = await agent.run("What is the meaning of life?")
    assert result.answer == "The answer is 42."
    assert result.total_iterations == 1
    assert result.provider == "gemini"


@pytest.mark.asyncio
async def test_agent_executes_single_tool_call():
    def adder(a: int, b: int) -> dict:
        """Add two numbers."""
        return {"success": True, "output": str(a + b), "error": None}

    router = MockLLMRouter([
        LLMResponse(
            content="I will add the numbers.",
            tool_calls=[{"name": "adder", "arguments": {"a": 2, "b": 3}}],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
        LLMResponse(
            content="The sum is 5.",
            tool_calls=[],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
    ])

    agent = ReActAgent(llm_router=router, tools={"adder": adder})
    result = await agent.run("Add 2 and 3")
    assert result.answer == "The sum is 5."
    assert result.total_iterations == 2
    assert len(result.steps) == 2
    assert result.steps[0].tool_calls[0].name == "adder"
    assert result.steps[0].tool_results[0].output == "5"


@pytest.mark.asyncio
async def test_agent_handles_tool_failure():
    def breaker() -> dict:
        """Always breaks."""
        raise RuntimeError("boom")

    router = MockLLMRouter([
        LLMResponse(
            content="I will run it.",
            tool_calls=[{"name": "breaker", "arguments": {}}],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
        LLMResponse(
            content="The tool failed, but I can still help.",
            tool_calls=[],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
    ])

    agent = ReActAgent(llm_router=router, tools={"breaker": breaker})
    result = await agent.run("Run breaker")
    assert result.answer == "The tool failed, but I can still help."
    assert result.steps[0].tool_results[0].success is False
    assert "boom" in result.steps[0].tool_results[0].error


@pytest.mark.asyncio
async def test_agent_respects_max_iterations():
    router = MockLLMRouter([
        LLMResponse(
            content="Still working...",
            tool_calls=[{"name": "noop", "arguments": {}}],
            model_used="gemini-pro",
            provider="gemini",
            call_log=LLMCallLog(model="gemini-pro", provider="gemini", latency_ms=100.0, success=True),
        ),
    ])

    def noop() -> dict:
        return {"success": True, "output": "ok", "error": None}

    agent = ReActAgent(llm_router=router, tools={"noop": noop})
    agent.MAX_ITERATIONS = 3
    result = await agent.run("Loop forever")
    assert result.total_iterations == 3
    assert "max iterations" in result.answer.lower()
