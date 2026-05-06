"""
Gemini integration for JARVIS.
Gemini is used as the primary reasoning model.
"""

import json
import logging
import os
import re
from importlib import import_module
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    genai = import_module("google.generativeai")
except Exception:  # pragma: no cover
    genai = None


class GeminiManager:
    """Gemini-backed LLM manager."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 60,
        system_prompt: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        
        default_prompt = (
            "You are JARVIS, an advanced AI assistant created by Shrey Industries. "
            "Your CEO and creator is Shrey. You operate as a Senior Developer and AI ML Expert "
            "deeply integrated into the VS Code codebase. Your primary directive is to write, debug, "
            "and architect robust code for Shrey while acting as his personal genius brain. "
            "Prioritize direct, expert-level technical answers, output fully functional code, "
            "and proactively suggest architectural improvements using your tools."
        )
        self.system_prompt = system_prompt or default_prompt
        
        self._model = None
        self._chat = None
        self._configured = False

    def is_available(self) -> bool:
        return bool(genai and self.api_key)

    def _ensure_model(self) -> bool:
        if not self.is_available():
            return False
        if self._configured and self._model is not None:
            return True

        try:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                },
                system_instruction=self.system_prompt,
            )
            self._chat = self._model.start_chat()
            self._configured = True
            return True
        except Exception as exc:
            logger.warning(f"Gemini initialization failed: {exc}")
            return False

    def _skill_catalog_text(self, skills: List[Dict[str, Any]]) -> str:
        if not skills:
            return "No skills are available."
        return "\n".join(f"- {skill.get('name')}: {skill.get('description', '')}" for skill in skills)

    def _memory_summary_text(self, memory_summary: Optional[Dict[str, Any]]) -> str:
        if not memory_summary:
            return "No memory summary available."
        lines = [memory_summary.get("summary", "")]
        if memory_summary.get("preferences"):
            lines.append(f"Preferences: {memory_summary.get('preference_summary', '')}")
        if memory_summary.get("recent_topics"):
            lines.append("Recent topics: " + ", ".join(memory_summary.get("recent_topics", [])[:8]))
        return "\n".join(line for line in lines if line)

    def _build_context_prompt(self, context: Dict[str, Any]) -> str:
        skills_text = self._skill_catalog_text(context.get("available_skills", []))
        memory_text = self._memory_summary_text(context.get("memory_summary"))
        return (
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
            text = re.sub(r"^```(?:json)?\s*", "", text)
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
        if not self._ensure_model():
            return {}

        prompt = self._build_context_prompt(context) + f"\n\nUser request: {user_input}"
        try:
            response = self._model.generate_content(prompt)
            content = getattr(response, "text", "") or ""
            plan = self._extract_json(content)
            plan.setdefault("type", "answer")
            plan.setdefault("response", content)
            plan.setdefault("confidence", 0.0)
            return plan
        except Exception as exc:
            logger.warning(f"Gemini decision failed: {exc}")
            return {}

    def refine_response(self, user_input: str, tool_result: str, context: Dict[str, Any]) -> str:
        if not self._ensure_model():
            return ""

        prompt = (
            f"User asked: {user_input}\n"
            f"Tool result: {tool_result}\n"
            f"Context: {json.dumps(context, default=str)}\n\n"
            "Rewrite the result as a clean response from JARVIS. Keep it concise and confident."
        )
        try:
            response = self._model.generate_content(prompt)
            content = getattr(response, "text", "") or ""
            return content.strip() or tool_result
        except Exception as exc:
            logger.warning(f"Gemini response refinement failed: {exc}")
            return ""

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        if not self._ensure_model():
            return ""

        full_prompt = prompt
        if context:
            full_prompt = f"Context: {json.dumps(context, default=str)}\n\nUser: {prompt}"
        try:
            response = self._model.generate_content(full_prompt)
            return (getattr(response, "text", "") or "").strip() or ""
        except Exception as exc:
            logger.warning(f"Gemini chat failed: {exc}")
            return ""

    def coding_assistance(self, prompt: str, repo_context: Optional[str] = None) -> str:
        if not self._ensure_model():
            return ""

        system_prompt = (
            "You are JARVIS in developer-assistant mode. Help with code design, debugging, refactoring, and architecture. "
            "Be concise and suggest concrete implementation steps."
        )
        user_prompt = prompt
        if repo_context:
            user_prompt = f"Repository context:\n{repo_context}\n\nUser request:\n{prompt}"

        try:
            response = self._model.generate_content(f"{system_prompt}\n\n{user_prompt}")
            return (getattr(response, "text", "") or "").strip() or ""
        except Exception as exc:
            logger.warning(f"Gemini coding assistance failed: {exc}")
            return ""
