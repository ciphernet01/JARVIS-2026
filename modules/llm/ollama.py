"""
Ollama integration for JARVIS.
Provides structured local LLM responses and tool-selection planning.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class OllamaPlan:
    """Structured decision returned by the LLM."""
    type: str = "answer"
    response: str = ""
    skill_name: Optional[str] = None
    skill_query: Optional[str] = None
    confidence: float = 0.0


class OllamaManager:
    """Local LLM client for JARVIS using Ollama's HTTP API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 60,
        system_prompt: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are JARVIS, a concise and capable assistant. "
            "Prefer direct answers. When a tool or skill should be used, return JSON only with the tool choice."
        )

    def is_available(self) -> bool:
        """Check whether Ollama is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def _skill_catalog_text(self, skills: List[Dict[str, Any]]) -> str:
        if not skills:
            return "No skills are available."

        lines = []
        for skill in skills:
            lines.append(
                f"- {skill.get('name')}: {skill.get('description', '')}"
            )
        return "\n".join(lines)

    def _memory_summary_text(self, memory_summary: Optional[Dict[str, Any]]) -> str:
        if not memory_summary:
            return "No memory summary available."

        lines = [memory_summary.get("summary", "")]
        if memory_summary.get("preferences"):
            lines.append(f"Preferences: {memory_summary.get('preference_summary', '')}")
        if memory_summary.get("recent_topics"):
            lines.append("Recent topics: " + ", ".join(memory_summary.get("recent_topics", [])[:8]))
        return "\n".join(line for line in lines if line)

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        skills_text = self._skill_catalog_text(context.get("available_skills", []))
        memory_text = self._memory_summary_text(context.get("memory_summary"))
        return (
            f"{self.system_prompt}\n\n"
            f"User name: {context.get('user_name', 'Sir')}\n"
            f"Current user id: {context.get('user_id', 'unknown')}\n"
            f"Assistant status: {json.dumps(context.get('status', {}), default=str)}\n\n"
            f"Memory:\n{memory_text}\n\n"
            f"Available skills:\n{skills_text}\n\n"
            "Return ONLY valid JSON with one of these shapes:\n"
            "1) {\"type\": \"answer\", \"response\": \"...\", \"confidence\": 0.0-1.0}\n"
            "2) {\"type\": \"skill\", \"skill_name\": \"exact_skill_name\", \"skill_query\": \"query to pass\", \"response\": \"short preamble\", \"confidence\": 0.0-1.0}\n"
            "If you need no tool, choose answer. If you need a skill, use the exact skill name from the catalog."
        )

    def _extract_json(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\\s*", "", text)
            text = re.sub(r"```$", "", text).strip()

        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return {"type": "answer", "response": text}

    def decide_action(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask Ollama whether to answer directly or invoke a skill."""
        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
            "messages": [
                {"role": "system", "content": self._build_system_prompt(context)},
                {"role": "user", "content": user_input},
            ],
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            plan = self._extract_json(content)
            plan.setdefault("type", "answer")
            plan.setdefault("response", content)
            plan.setdefault("confidence", 0.0)
            return plan
        except Exception as exc:
            logger.warning(f"Ollama decision failed: {exc}")
            return {"type": "answer", "response": "", "confidence": 0.0, "error": str(exc)}

    def refine_response(
        self,
        user_input: str,
        tool_result: str,
        context: Dict[str, Any],
    ) -> str:
        """Turn a raw tool result into a natural JARVIS-style response."""
        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
            "messages": [
                {"role": "system", "content": self.system_prompt + " Keep responses short, precise, and confident."},
                {
                    "role": "user",
                    "content": (
                        f"User asked: {user_input}\n"
                        f"Tool result: {tool_result}\n"
                        f"Context: {json.dumps(context, default=str)}\n\n"
                        "Rewrite the result as a clean response from JARVIS."
                    ),
                },
            ],
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            return content or tool_result
        except Exception as exc:
            logger.warning(f"Ollama response refinement failed: {exc}")
            return tool_result

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Simple direct chat helper."""
        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        if context:
            payload["messages"].insert(
                1,
                {"role": "system", "content": f"Context: {json.dumps(context, default=str)}"},
            )

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning(f"Ollama chat failed: {exc}")
            return f"I couldn't reach the local model at {self.base_url}."

    def coding_assistance(self, prompt: str, repo_context: Optional[str] = None) -> str:
        """Developer-focused assistant mode for code and architecture help."""
        system_prompt = (
            "You are JARVIS in developer-assistant mode. "
            "Help with code design, debugging, refactoring, and architecture. "
            "Be concise, practical, and suggest concrete implementation steps."
        )
        user_prompt = prompt
        if repo_context:
            user_prompt = f"Repository context:\n{repo_context}\n\nUser request:\n{prompt}"

        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning(f"Ollama coding assistance failed: {exc}")
            return f"I couldn't reach the local model at {self.base_url}."
