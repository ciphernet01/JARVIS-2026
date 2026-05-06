"""
Proactive Manager
Generates briefings and alerts from assistant, memory, and persistence state.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProactiveManager:
    """Build proactive briefings and alerts for the active user."""

    def __init__(self, assistant, persistence_components: Optional[Dict[str, Any]] = None):
        self.assistant = assistant
        self.persistence = persistence_components or {}

    def _resolve_user_id(self, user_id: Optional[str] = None) -> Optional[str]:
        if user_id:
            return user_id
        return getattr(self.assistant, "current_user_id", None)

    def _task_store(self):
        return self.persistence.get("task_store")

    def _conversation_store(self):
        return self.persistence.get("conversation_store")

    def _preference_store(self):
        return self.persistence.get("preference_store")

    def _normalize_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        next_execution = task.get("next_execution")
        next_text = None
        if next_execution:
            next_text = str(next_execution)
        return {
            "id": task.get("id"),
            "name": task.get("task_name") or task.get("name") or "Untitled task",
            "schedule": task.get("schedule"),
            "status": task.get("status"),
            "next_execution": next_text,
            "last_executed": task.get("last_executed"),
        }

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None

    def get_upcoming_tasks(self, user_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Return tasks that deserve attention soon."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return []

        store = self._task_store()
        if not store:
            return []

        tasks = store.get_user_tasks(resolved_user) or []
        upcoming: List[Dict[str, Any]] = []
        now = datetime.now()

        for task in tasks:
            normalized = self._normalize_task(task)
            status = (normalized.get("status") or "").lower()
            next_execution = self._parse_datetime(normalized.get("next_execution"))

            is_pending = status in {"pending", "scheduled"}
            is_due = next_execution is not None and next_execution <= now

            if is_pending or is_due:
                upcoming.append(normalized)

        upcoming.sort(key=lambda item: (item.get("next_execution") or "", item.get("name") or ""))
        return upcoming[:limit]

    def build_alerts(
        self,
        user_id: Optional[str] = None,
        system_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build a ranked list of proactive alerts."""
        resolved_user = self._resolve_user_id(user_id)
        alerts: List[Dict[str, Any]] = []

        if resolved_user:
            for task in self.get_upcoming_tasks(resolved_user, limit=5):
                alerts.append({
                    "type": "task",
                    "priority": "high" if (task.get("status") or "").lower() == "pending" else "medium",
                    "title": f"Task: {task['name']}",
                    "detail": task,
                })

        if system_metrics:
            memory = system_metrics.get("memory", {}) or {}
            disk = system_metrics.get("disk", {}) or {}
            cpu = system_metrics.get("cpu", {}) or {}

            memory_percent = memory.get("percent")
            disk_percent = disk.get("percent")
            cpu_percent = cpu.get("percent")

            if isinstance(memory_percent, (int, float)) and memory_percent >= 85:
                alerts.append({
                    "type": "system",
                    "priority": "high",
                    "title": "Memory pressure detected",
                    "detail": f"Memory usage is at {memory_percent}%.",
                })
            if isinstance(disk_percent, (int, float)) and disk_percent >= 90:
                alerts.append({
                    "type": "system",
                    "priority": "high",
                    "title": "Disk space warning",
                    "detail": f"Disk usage is at {disk_percent}%.",
                })
            if isinstance(cpu_percent, (int, float)) and cpu_percent >= 90:
                alerts.append({
                    "type": "system",
                    "priority": "medium",
                    "title": "CPU usage elevated",
                    "detail": f"CPU usage is at {cpu_percent}%.",
                })

        memory_summary = self.assistant.get_memory_summary(limit=6) if hasattr(self.assistant, "get_memory_summary") else None
        if memory_summary:
            recent_topics = memory_summary.get("recent_topics", []) or []
            if recent_topics:
                alerts.append({
                    "type": "context",
                    "priority": "low",
                    "title": "Recent conversation themes",
                    "detail": ", ".join(recent_topics[:5]),
                })

        return alerts

    def build_briefing(
        self,
        user_id: Optional[str] = None,
        system_metrics: Optional[Dict[str, Any]] = None,
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a morning/evening style briefing payload."""
        resolved_user = self._resolve_user_id(user_id)
        memory_summary = self.assistant.get_memory_summary(limit=8) if hasattr(self.assistant, "get_memory_summary") else None
        upcoming_tasks = self.get_upcoming_tasks(resolved_user, limit=5)
        alerts = self.build_alerts(resolved_user, system_metrics=system_metrics)

        preferences = {}
        if memory_summary:
            preferences = memory_summary.get("preferences", {}) or {}

        greeting_name = None
        if hasattr(self.assistant, "user_context"):
            greeting_name = self.assistant.user_context.get("user_name")

        salutation = f"Good day, {greeting_name}." if greeting_name else "Good day."

        lines = [salutation]

        if weather:
            description = weather.get("description") or "current weather is unavailable"
            location = weather.get("location") or "your area"
            temp = weather.get("temp_c")
            if temp not in (None, ""):
                lines.append(f"Weather in {location}: {temp}°C and {description}.")
            else:
                lines.append(f"Weather in {location}: {description}.")

        # Autonomous News Injection
        if self.assistant.skill_registry:
            news_skill = self.assistant.skill_registry.skills.get("news_skill")
            if news_skill:
                try:
                    news_report = news_skill.execute("", {})
                    if "headlines" in news_report.lower():
                        lines.append(news_report)
                except Exception:
                    pass

        if upcoming_tasks:
            task_names = [task.get("name", "Task") for task in upcoming_tasks[:3]]
            lines.append("Upcoming tasks: " + "; ".join(task_names) + ".")
        else:
            lines.append("No urgent tasks are queued right now.")

        if alerts:
            high_priority = [a for a in alerts if a.get("priority") == "high"]
            if high_priority:
                lines.append(f"Priority alerts: {len(high_priority)} item(s) need attention.")

        if memory_summary:
            recent_topics = memory_summary.get("recent_topics", []) or []
            if recent_topics:
                lines.append("Recent focus: " + ", ".join(recent_topics[:5]) + ".")

        if preferences:
            pref_bits = []
            for key in ("voice_gender", "speech_rate", "language", "theme"):
                value = preferences.get(key)
                if value not in (None, ""):
                    pref_bits.append(f"{key.replace('_', ' ')}={value}")
            if pref_bits:
                lines.append("Preferences: " + ", ".join(pref_bits) + ".")

        return {
            "user_id": resolved_user,
            "generated_at": datetime.now().isoformat(),
            "summary": " ".join(lines),
            "lines": lines,
            "memory": memory_summary,
            "upcoming_tasks": upcoming_tasks,
            "alerts": alerts,
            "weather": weather,
        }

    def build_briefing_text(self, **kwargs) -> str:
        """Return the briefing as a single assistant-friendly string."""
        payload = self.build_briefing(**kwargs)
        return " ".join(payload.get("lines", []))
