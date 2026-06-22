"""Provider-neutral client for local OpenAI-compatible inference runtimes."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalRuntimeCapabilities:
    provider: str
    base_url: str
    reachable: bool
    configured_model: str
    available_models: List[str]
    configured_model_available: bool
    openai_compatible: bool = True
    tool_calling: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OpenAICompatibleManager:
    """Local inference manager shared by Ollama, vLLM, and llama.cpp servers."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5-coder:7b",
        provider: str = "local",
        api_key: str = "local",
        temperature: float = 0.2,
        top_p: float = 0.9,
        timeout_seconds: int = 60,
        system_prompt: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.api_key = api_key or "local"
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt or (
            "You are A.S.T.R.A, a concise local operating-system intelligence. "
            "Use tools only through the authorized control plane."
        )

    @property
    def headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def capabilities(self) -> LocalRuntimeCapabilities:
        models: List[str] = []
        reachable = False
        try:
            response = requests.get(
                f"{self.base_url}/models", headers=self.headers, timeout=min(3, self.timeout_seconds)
            )
            response.raise_for_status()
            data = response.json()
            models = [
                item.get("id")
                for item in data.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            reachable = True
        except Exception as exc:
            logger.debug("Local inference capability probe failed: %s", exc)
        return LocalRuntimeCapabilities(
            provider=self.provider,
            base_url=self.base_url,
            reachable=reachable,
            configured_model=self.model,
            available_models=models,
            configured_model_available=self.model in models,
        )

    def is_available(self) -> bool:
        return self.capabilities().reachable

    def _completion(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise RuntimeError("Local inference runtime returned no choices")
        message = choices[0].get("message") or {}
        if not isinstance(message, dict):
            raise RuntimeError("Local inference runtime returned an invalid message")
        return message

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.append({"role": "system", "content": f"Context: {json.dumps(context, default=str)}"})
        messages.append({"role": "user", "content": prompt})
        try:
            return str(self._completion(messages).get("content") or "").strip()
        except Exception as exc:
            logger.warning("%s chat failed: %s", self.provider, exc)
            return ""

    def decide_action(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        skills = context.get("available_skills", [])
        instruction = (
            f"{self.system_prompt}\nAvailable skills: {json.dumps(skills, default=str)}\n"
            "Return JSON only: either {\"type\":\"answer\",\"response\":\"...\"} or "
            "{\"type\":\"skill\",\"skill_name\":\"...\",\"skill_query\":\"...\"}."
        )
        try:
            content = str(
                self._completion(
                    [{"role": "system", "content": instruction}, {"role": "user", "content": user_input}]
                ).get("content")
                or ""
            ).strip()
            fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
            result = json.loads(fenced)
            if isinstance(result, dict):
                result.setdefault("confidence", 0.0)
                return result
        except Exception as exc:
            logger.warning("%s action decision failed: %s", self.provider, exc)
        return {"type": "answer", "response": "", "confidence": 0.0}

    def refine_response(self, user_input: str, tool_result: str, context: Dict[str, Any]) -> str:
        prompt = f"User request: {user_input}\nTool result: {tool_result}\nRespond concisely."
        return self.chat(prompt, context) or tool_result

    def coding_assistance(self, prompt: str, repo_context: Optional[str] = None) -> str:
        context = {"repository": repo_context} if repo_context else None
        return self.chat(prompt, context)
