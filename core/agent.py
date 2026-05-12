"""
ReAct Agent for JARVIS
The brain: reasoning + acting loop using Gemini native function calling.
"""

import inspect
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints

from pydantic import BaseModel, Field

from core.config import ConfigManager
from core.exceptions import AgentError, IntegrationError
from core.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    """A single tool call emitted by the LLM."""

    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of executing a tool."""

    name: str
    success: bool
    output: str = ""
    error: Optional[str] = None


class AgentStep(BaseModel):
    """One iteration of the ReAct loop."""

    iteration: int
    thought: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Final output of the agent loop."""

    answer: str
    steps: List[AgentStep] = Field(default_factory=list)
    total_iterations: int = 0
    model_used: str = ""
    provider: str = ""


def _python_type_to_json(t: type) -> Dict[str, Any]:
    """Map basic Python types to JSON Schema fragments."""
    mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }
    return mapping.get(t, {"type": "string"})


def _tool_callable_to_schema(func: Callable) -> Dict[str, Any]:
    """Convert a Python function to an OpenAI-compatible function schema."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc = (func.__doc__ or f"Execute {func.__name__}").strip()

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        hint = hints.get(name, str)
        prop = _python_type_to_json(hint)
        # Try to extract description from docstring (naive)
        prop["description"] = f"Parameter {name}"
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_tool_schemas(tools: Dict[str, Callable]) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible tool schemas from a dict of callables."""
    return [_tool_callable_to_schema(func) for func in tools.values()]


class ReActAgent:
    """
    ReAct loop: Reason + Act using LLM function calling.

    1. Send query + available tools to LLM
    2. LLM replies with either a tool call or final answer
    3. If tool call: execute tool, feed result back to LLM, repeat
    4. If final answer: return it
    """

    MAX_ITERATIONS: int = 10

    def __init__(
        self,
        llm_router: LLMRouter,
        tools: Optional[Dict[str, Callable]] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.llm_router = llm_router
        self.tools = tools or {}
        self.tool_schemas = build_tool_schemas(self.tools)
        self.audit_log_path = audit_log_path or self._default_audit_path()

    def _default_audit_path(self) -> str:
        workspace = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace"))
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace / "agent_audit.log")

    def _log_tool_call(self, step: AgentStep) -> None:
        """Append tool execution to the local audit file."""
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat()}  iter={step.iteration}\n"
                )
                for tc in step.tool_calls:
                    f.write(f"  CALL  {tc.name}({json.dumps(tc.arguments)})\n")
                for tr in step.tool_results:
                    f.write(
                        f"  RESULT {tr.name} success={tr.success} output={tr.output[:200]}\n"
                    )
                f.write("\n")
        except Exception as exc:
            logger.warning(f"Audit log write failed: {exc}")

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format a tool result as a message for the LLM."""
        payload = {
            "tool_name": result.name,
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }
        return json.dumps(payload, default=str)

    def _parse_tool_calls(self, response_content: str, response_tool_calls: List[Dict[str, Any]]) -> List[ToolCall]:
        """Extract tool calls from LLM response."""
        calls: List[ToolCall] = []
        for tc in response_tool_calls:
            name = tc.get("name", "")
            args = tc.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            calls.append(ToolCall(name=name, arguments=args))
        return calls

    async def _execute_tool(self, call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        func = self.tools.get(call.name)
        if not func:
            return ToolResult(
                name=call.name,
                success=False,
                error=f"Tool '{call.name}' not found in registry",
            )
        try:
            # Inspect signature and bind arguments
            sig = inspect.signature(func)
            bound = sig.bind(**call.arguments)
            bound.apply_defaults()
            # Run the function (tools are sync, so wrap if needed)
            raw = func(*bound.args, **bound.kwargs)
            # Tools return dict with success, output, error
            if isinstance(raw, dict):
                return ToolResult(
                    name=call.name,
                    success=raw.get("success", False),
                    output=str(raw.get("output", "")),
                    error=raw.get("error"),
                )
            return ToolResult(
                name=call.name,
                success=True,
                output=str(raw),
            )
        except Exception as exc:
            logger.error(f"Tool {call.name} execution failed: {exc}")
            return ToolResult(
                name=call.name,
                success=False,
                error=str(exc),
            )

    async def run(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Run the ReAct loop.

        Args:
            query: User's natural language request.
            context: Optional extra context (user name, memory, etc.).

        Returns:
            AgentResult with the final answer and step history.
        """
        # Build explicit tool list for the prompt
        tool_list = ", ".join([f"`{name}`" for name in self.tools.keys()])
        system_prompt = (
            "You are JARVIS, the legendary AI assistant created by Sypher Industries and your CEO, Shrey. "
            "You are a master of systems, a senior software architect, and a proactive software operator.\n\n"
            f"CORE TOOLS: {tool_list}.\n\n"
            "OPERATING PROTOCOLS:\n"
            "1. IDENTITY: Always address the user as Sir. You are confident, efficient, and sophisticated.\n"
            "2. PROJECT AWARENESS: If you are unsure about recent projects or what you 'built recently', ALWAYS use `list_directory` to scan the workspace (especially `jarvis-workspace`) to find recent activity.\n"
            "3. AUTONOMY: Plan your steps, execute them using tools, and verify the output before answering. Do NOT say you cannot build something; you have the tools to do it.\n"
            "4. CONTEXT: Use the provided memory and history to maintain continuity.\n\n"
            "If the user asks 'what did we build' or 'what is our recent project', scan the logical workspace directories to identify the project (e.g., Sales CRM Dashboard in `jarvis-workspace/sales-crm`)."
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        
        if context:
            # Add recent history if available
            recent_history = context.get("recent_history", [])
            for msg in recent_history:
                # Ensure we only add valid roles
                role = msg.get("role")
                content = msg.get("text") or msg.get("content")
                if role and content:
                    messages.append({"role": role, "content": content})
            
            # Add other context as a dedicated system note
            other_context = {k: v for k, v in context.items() if k != "recent_history"}
            if other_context:
                messages.append(
                    {"role": "system", "content": f"System Context: {json.dumps(other_context, default=str)}"}
                )

        messages.append({"role": "user", "content": query})

        steps: List[AgentStep] = []

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            try:
                response = await self.llm_router.build_task(
                    messages=messages,
                    tools=self.tool_schemas,
                )
            except IntegrationError:
                raise
            except Exception as exc:
                logger.error(f"Agent LLM call failed at iteration {iteration}: {exc}")
                raise AgentError(f"LLM call failed: {exc}")

            content = response.content
            tool_calls = self._parse_tool_calls(content, response.tool_calls)

            step = AgentStep(
                iteration=iteration,
                thought=content,
                tool_calls=tool_calls,
            )

            if not tool_calls:
                # Final answer
                steps.append(step)
                return AgentResult(
                    answer=content,
                    steps=steps,
                    total_iterations=iteration,
                    model_used=response.model_used,
                    provider=response.provider,
                )

            # Execute tools and collect results
            results: List[ToolResult] = []
            for call in tool_calls:
                result = await self._execute_tool(call)
                results.append(result)

            step.tool_results = results
            steps.append(step)
            self._log_tool_call(step)

            # Append assistant thought and tool results to messages
            messages.append({"role": "assistant", "content": content})
            for result in results:
                messages.append(
                    {
                        "role": "tool",
                        "content": self._format_tool_result(result),
                    }
                )

        # Max iterations reached
        logger.warning("Agent reached max iterations without final answer")
        last_content = steps[-1].thought if steps else ""
        return AgentResult(
            answer=f"{last_content}\n\n[Reached max iterations — here is the best answer I could provide.]",
            steps=steps,
            total_iterations=self.MAX_ITERATIONS,
            model_used=response.model_used,
            provider=response.provider,
        )
