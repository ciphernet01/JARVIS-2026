"""
Skills Module
"""

from .base import Skill, SkillRegistry
from .builtin import (
    TimeSkill,
    DateSkill,
    GreetingSkill,
    HelpSkill,
    StatusSkill,
)
from .integration_skills import (
    WebSearchSkill,
    WeatherSkill,
    SystemInfoSkill,
    ReminderSkill,
    CalendarSkill,
    EmailSkill,
    OpenLinkSkill,
)
from .news import NewsSkill
from .builder import BuilderSkill
from .factory import SkillFactory

__all__ = [
    "Skill",
    "SkillRegistry",
    "TimeSkill",
    "DateSkill",
    "GreetingSkill",
    "HelpSkill",
    "StatusSkill",
    "WebSearchSkill",
    "OpenLinkSkill",
    "WeatherSkill",
    "SystemInfoSkill",
    "ReminderSkill",
    "CalendarSkill",
    "EmailSkill",
    "NewsSkill",
    "BuilderSkill",
    "SkillFactory",
]
