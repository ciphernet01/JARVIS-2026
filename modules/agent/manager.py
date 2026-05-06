"""
Agent Manager
Plans and executes multi-step workflows for JARVIS.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentManager:
    """Plan and execute multi-step workflows."""

    def __init__(self, llm_manager: Optional[Any] = None, skill_registry: Optional[Any] = None, persistence_components: Optional[Dict[str, Any]] = None):
        self.llm_manager = llm_manager
        self.skill_registry = skill_registry
        self.persistence = persistence_components or {}

    def is_enabled(self) -> bool:
        return bool(self.llm_manager and self.skill_registry)

    def should_plan(self, user_input: str) -> bool:
        text = (user_input or "").lower()
        triggers = ["then", "after that", "workflow", "plan", "build", "create", "multi-step", "sequence", "and also", "combine"]
        return any(trigger in text for trigger in triggers)

    def _available_skills(self) -> List[Dict[str, Any]]:
        if not self.skill_registry:
            return []
        if hasattr(self.skill_registry, "list_skills"):
            try:
                return self.skill_registry.list_skills()
            except Exception:
                pass
        skills_obj = getattr(self.skill_registry, "skills", {})
        if isinstance(skills_obj, dict):
            items = []
            for name, skill in skills_obj.items():
                if callable(getattr(skill, "get_info", None)):
                    try:
                        items.append(skill.get_info())
                        continue
                    except Exception:
                        pass
                items.append({"name": name, "description": getattr(skill, "description", "")})
            return items
        return []

    def _memory_context(self, context: Dict[str, Any]) -> str:
        memory_summary = context.get("memory_summary") or {}
        lines = [memory_summary.get("summary", "")]
        if memory_summary.get("recent_topics"):
            lines.append("Recent topics: " + ", ".join(memory_summary.get("recent_topics", [])[:6]))
        if memory_summary.get("preferences"):
            lines.append(f"Preferences: {memory_summary.get('preference_summary', '')}")
        return "\n".join(line for line in lines if line)

    def _build_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        skills_text = "\n".join(
            f"- {item.get('name')}: {item.get('description', '')}"
            for item in self._available_skills()
        ) or "No skills available."
        return (
            "You are JARVIS operating as a workflow planner. "
            "Break the user request into a concise execution plan using available skills when appropriate. "
            "Return ONLY valid JSON with this shape:\n"
            "{\n"
            "  \"type\": \"workflow\",\n"
            "  \"summary\": \"short summary\",\n"
            "  \"steps\": [\n"
            "    {\"id\": \"1\", \"type\": \"skill|chat|question|note\", \"title\": \"...\", \"skill_name\": \"...\", \"input\": \"...\", \"description\": \"...\"}\n"
            "  ]\n"
            "}\n\n"
            f"User name: {context.get('user_name', 'Sir')}\n"
            f"Memory:\n{self._memory_context(context)}\n\n"
            f"Available skills:\n{skills_text}\n\n"
            f"User request: {user_input}"
        )

    def _parse_plan(self, content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except Exception:
            return {
                "type": "workflow",
                "summary": text[:200] if text else "Workflow plan",
                "steps": []
            }

    def build_plan(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.llm_manager:
            return {
                "type": "workflow",
                "summary": user_input,
                "steps": [
                    {
                        "id": "1",
                        "type": "chat",
                        "title": "Respond directly",
                        "input": user_input,
                        "description": "No LLM manager available, provide a direct answer."
                    }
                ],
            }

        prompt = self._build_prompt(user_input, context)
        try:
            response = self.llm_manager.chat(prompt, context=context)
            plan = self._parse_plan(response)
            plan.setdefault("type", "workflow")
            plan.setdefault("summary", user_input)
            plan.setdefault("steps", [])
            return plan
        except Exception as exc:
            logger.warning(f"Workflow planning failed: {exc}")
            return {
                "type": "workflow",
                "summary": user_input,
                "steps": [],
                "error": str(exc),
            }

    def _audit(self, action: str, details: Dict[str, Any], success: bool = True) -> None:
        audit_logger = self.persistence.get("audit_logger")
        if audit_logger:
            try:
                audit_logger.log_action(
                    user_id=details.get("user_id"),
                    action=action,
                    details=details,
                    success=success,
                )
            except Exception as exc:
                logger.warning(f"Audit log failed: {exc}")

    def execute_plan(self, plan: Dict[str, Any], user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        steps = plan.get("steps", []) or []
        results: List[Dict[str, Any]] = []

        self._audit(
            "agent_plan_started",
            {
                "user_id": context.get("user_id"),
                "summary": plan.get("summary", user_input),
                "step_count": len(steps),
            },
            success=True,
        )

        for index, step in enumerate(steps, start=1):
            step_type = (step.get("type") or "note").lower()
            step_payload = {
                "index": index,
                "id": step.get("id", str(index)),
                "type": step_type,
                "title": step.get("title", f"Step {index}"),
                "skill_name": step.get("skill_name"),
                "input": step.get("input") or user_input,
                "description": step.get("description", ""),
            }

            try:
                if step_type == "skill" and self.skill_registry:
                    skill_name = step_payload.get("skill_name")
                    skill_query = step_payload.get("input")
                    if skill_name and hasattr(self.skill_registry, "execute_skill"):
                        result = self.skill_registry.execute_skill(skill_name, skill_query, context)
                    else:
                        result = self.skill_registry.execute_query(skill_query, context)
                    step_payload["result"] = result
                    step_payload["success"] = bool(result)
                elif step_type == "chat" and self.llm_manager:
                    step_payload["result"] = self.llm_manager.chat(step_payload.get("input", user_input), context=context)
                    step_payload["success"] = True
                elif step_type == "question":
                    step_payload["result"] = step_payload.get("description") or "Clarification required."
                    step_payload["success"] = True
                else:
                    step_payload["result"] = step_payload.get("description") or step_payload.get("input")
                    step_payload["success"] = True
            except Exception as exc:
                step_payload["result"] = f"Error: {exc}"
                step_payload["success"] = False
                logger.error(f"Workflow step failed: {exc}")

            results.append(step_payload)
            self._audit(
                "agent_step_completed",
                {
                    "user_id": context.get("user_id"),
                    "step": step_payload,
                },
                success=step_payload.get("success", False),
            )

            if step_type == "question":
                break

        summary_text = self._summarize_results(user_input, plan, results, context)
        self._audit(
            "agent_plan_completed",
            {
                "user_id": context.get("user_id"),
                "summary": summary_text,
                "step_count": len(results),
            },
            success=True,
        )

        return {
            "type": "workflow_result",
            "summary": summary_text,
            "steps": results,
        }

    def _summarize_results(self, user_input: str, plan: Dict[str, Any], results: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        if self.llm_manager and results:
            raw = "\n".join(
                f"{item.get('title')}: {item.get('result')}"
                for item in results
            )
            try:
                return self.llm_manager.refine_response(
                    user_input,
                    f"Workflow summary:\n{raw}",
                    context,
                ) or raw
            except Exception:
                return raw

        if results:
            return " ".join(str(item.get("result", "")).strip() for item in results if item.get("result"))
        return plan.get("summary", user_input)
