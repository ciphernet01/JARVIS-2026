"""
Builder Skill for JARVIS
Autonomous app scaffolding on top of the ReAct agent loop.
"""

import logging
from typing import Any, Dict, List

from modules.skills.base import Skill

logger = logging.getLogger(__name__)


class BuilderSkill(Skill):
    """
    Skill that triggers the ReAct agent to scaffold, build, and run apps.
    When the user says 'build me...' or 'create...', this skill delegates
    to the agent loop which uses write_file, run_shell, and run_python tools.
    """

    @property
    def keywords(self) -> List[str]:
        return [
            "build me",
            "create",
            "scaffold",
            "make an app",
            "make a",
            "generate",
            "write a program",
            "develop",
            "deploy",
        ]

    @property
    def description(self) -> str:
        return "Autonomously scaffold, build, and run applications using the ReAct agent loop."

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        """
        The builder skill does not execute directly; it signals the assistant
        to route this query through the ReAct agent loop. Return a marker
        that the assistant layer replaces with an actual agent invocation.
        """
        logger.info(f"BuilderSkill triggered for: {query}")
        return "[BUILDER_TRIGGER]"
