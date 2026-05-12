"""
Built-in Skills for JARVIS
Common functionality skills
"""

import logging
from typing import Any, Dict, List
import datetime
from .base import Skill

logger = logging.getLogger(__name__)


class TimeSkill(Skill):
    """Tell current time"""

    def __init__(self):
        super().__init__("time_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["what time", "current time", "tell time", "what is the time"]

    @property
    def description(self) -> str:
        return "Tell the current time"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        response = f"The current time is {current_time}"
        logger.info(f"Time query executed: {response}")
        return response


class DateSkill(Skill):
    """Tell current date"""

    def __init__(self):
        super().__init__("date_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        return ["what date", "today", "what is today", "current date"]

    @property
    def description(self) -> str:
        return "Tell the current date"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        today = datetime.date.today().strftime("%A, %B %d, %Y")
        response = f"Today is {today}"
        logger.info(f"Date query executed: {response}")
        return response


class GreetingSkill(Skill):
    """Greet the user"""

    def __init__(self):
        super().__init__("greeting_skill", "1.0")

    @property
    def keywords(self) -> List[str]:
        # Narrow keywords to prevent interception of contextual queries
        return ["greet user", "say hello", "formal greeting"]

    @property
    def description(self) -> str:
        return "Greet the user"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        user_name = context.get("user_name", "Sir") if context else "Sir"
        response = f"{greeting}, {user_name}! I am JARVIS. How can I assist you today?"
        return response


class HelpSkill(Skill):
    """Show available skills"""

    def __init__(self):
        super().__init__("help_skill", "1.0")
        self.skill_registry = None

    @property
    def keywords(self) -> List[str]:
        return ["help", "what can you do", "skills", "abilities"]

    @property
    def description(self) -> str:
        return "Show available skills and help"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        if not self.skill_registry:
            return "Skill registry not available"

        skills = self.skill_registry.list_skills()
        response = "Available skills:\n"
        for skill_info in skills:
            if skill_info["enabled"]:
                response += f"- {skill_info['name']}: {skill_info['description']}\n"

        return response


class StatusSkill(Skill):
    """Get JARVIS status"""

    def __init__(self):
        super().__init__("status_skill", "1.0")
        self.skill_registry = None

    @property
    def keywords(self) -> List[str]:
        return ["status", "how are you", "what's up", "are you online"]

    @property
    def description(self) -> str:
        return "Report JARVIS status"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        if not self.skill_registry:
            return "I am online and ready to assist."

        stats = self.skill_registry.get_skill_stats()
        response = (
            f"I am online and ready to assist. "
            f"I have {stats['enabled_skills']} active skills available."
        )
        return response
