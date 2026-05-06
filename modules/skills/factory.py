"""
Skill Factory
Registers built-in and integration skills in one place
"""

import logging
from typing import Any, Dict

from .base import SkillRegistry
from .builtin import GreetingSkill, TimeSkill, DateSkill, HelpSkill, StatusSkill
from .integration_skills import WebSearchSkill, WeatherSkill, SystemInfoSkill, ReminderSkill, CalendarSkill, EmailSkill, CameraSkill, OpenLinkSkill
from .news import NewsSkill
from .developer import FileManagementSkill, ExecuteCommandSkill

logger = logging.getLogger(__name__)


class SkillFactory:
    """Create and configure the default skill registry"""

    @staticmethod
    def create_default_registry(context: Dict[str, Any] = None) -> SkillRegistry:
        registry = SkillRegistry()
        skills = [
            GreetingSkill(),
            TimeSkill(),
            DateSkill(),
            HelpSkill(),
            StatusSkill(),
            WebSearchSkill(),
            WeatherSkill(),
            SystemInfoSkill(),
            ReminderSkill(),
            CalendarSkill(),
            EmailSkill(),
            CameraSkill(),
            OpenLinkSkill(),
            NewsSkill(),
            FileManagementSkill(),
            ExecuteCommandSkill(),
        ]

        for skill in skills:
            registry.register(skill)

        for skill_name in ["help_skill", "status_skill"]:
            if skill_name in registry.skills:
                registry.skills[skill_name].skill_registry = registry

        logger.info(f"Registered {len(skills)} default skills")
        return registry
