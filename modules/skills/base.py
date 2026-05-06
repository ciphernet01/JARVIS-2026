"""
Skill System for JARVIS
Extensible command handling and execution
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class Skill(ABC):
    """Base class for all JARVIS skills"""

    def __init__(self, name: str, version: str = "1.0"):
        """
        Initialize skill

        Args:
            name: Name of the skill
            version: Version of the skill
        """
        self.name = name
        self.version = version
        self.enabled = True
        self.last_executed = None
        self.execution_count = 0

    @property
    @abstractmethod
    def keywords(self) -> List[str]:
        """
        Keywords that trigger this skill

        Example: ["wikipedia", "search on wikipedia", "look up"]
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Description of what this skill does
        """
        pass

    @abstractmethod
    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        """
        Execute the skill

        Args:
            query: User's command or query
            context: Additional context (user info, previous queries, etc.)

        Returns:
            Response to user
        """
        pass

    def can_handle(self, query: str) -> bool:
        """Check if this skill can handle the query"""
        query_lower = query.lower()
        for keyword in self.keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', query_lower):
                return True
        return False

    def before_execute(self, query: str) -> None:
        """Hook called before skill execution"""
        pass

    def after_execute(self, query: str, result: str) -> None:
        """Hook called after skill execution"""
        self.last_executed = datetime.now()
        self.execution_count += 1
        logger.info(f"Skill '{self.name}' executed (count: {self.execution_count})")

    def get_info(self) -> Dict[str, Any]:
        """Get skill information"""
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "keywords": self.keywords,
            "last_executed": self.last_executed,
            "execution_count": self.execution_count,
        }


class SkillRegistry:
    """Registry for managing skills"""

    def __init__(self):
        """Initialize skill registry"""
        self.skills: Dict[str, Skill] = {}
        self._keyword_index: List[Skill] = []
        self._query_cache: Dict[str, Optional[Skill]] = {}
        logger.info("Skill registry initialized")

    def _rebuild_index(self) -> None:
        """Rebuild the internal skill lookup index"""
        self._keyword_index = [skill for skill in self.skills.values() if skill.enabled]
        self._query_cache.clear()

    def register(self, skill: Skill) -> None:
        """
        Register a skill

        Args:
            skill: Skill instance to register
        """
        if skill.name in self.skills:
            logger.warning(f"Skill '{skill.name}' already registered, overwriting")

        self.skills[skill.name] = skill
        self._rebuild_index()
        logger.info(f"Registered skill: {skill.name} v{skill.version}")

    def unregister(self, skill_name: str) -> bool:
        """Unregister a skill"""
        if skill_name in self.skills:
            del self.skills[skill_name]
            self._rebuild_index()
            logger.info(f"Unregistered skill: {skill_name}")
            return True
        return False

    def find_skill(self, query: str) -> Optional[Skill]:
        """
        Find a skill that can handle the query

        Args:
            query: User's command or query

        Returns:
            Matching skill or None
        """
        query_lower = query.lower()
        cached = self._query_cache.get(query_lower)
        if query_lower in self._query_cache:
            return cached

        for skill in self._keyword_index:
            if not skill.enabled:
                continue
            if skill.can_handle(query_lower):
                self._query_cache[query_lower] = skill
                return skill

        self._query_cache[query_lower] = None
        return None

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(skill_name)

    def execute_skill(self, skill_name: str, query: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Execute a specific skill by name when an LLM selects a tool explicitly."""
        skill = self.get_skill(skill_name)
        if not skill or not skill.enabled:
            logger.warning(f"Skill not available: {skill_name}")
            return None

        try:
            skill.before_execute(query)
            result = skill.execute(query, context or {})
            skill.after_execute(query, result)
            return result
        except Exception as e:
            logger.error(f"Error executing skill '{skill.name}': {e}")
            return f"Error executing skill: {str(e)}"

    def execute_query(self, query: str, context: Dict[str, Any] = None) -> Optional[str]:
        """
        Execute a query using appropriate skill

        Args:
            query: User's command or query
            context: Additional context

        Returns:
            Response or None if no skill found
        """
        skill = self.find_skill(query)
        if not skill:
            logger.warning(f"No skill found for query: {query}")
            return None

        try:
            skill.before_execute(query)
            result = skill.execute(query, context or {})
            skill.after_execute(query, result)
            return result
        except Exception as e:
            logger.error(f"Error executing skill '{skill.name}': {e}")
            return f"Error executing skill: {str(e)}"

    def list_skills(self) -> List[Dict[str, Any]]:
        """Get list of all registered skills"""
        return [skill.get_info() for skill in self.skills.values()]

    def enable_skill(self, skill_name: str) -> bool:
        """Enable a skill"""
        if skill_name in self.skills:
            self.skills[skill_name].enabled = True
            self._rebuild_index()
            logger.info(f"Enabled skill: {skill_name}")
            return True
        return False

    def disable_skill(self, skill_name: str) -> bool:
        """Disable a skill"""
        if skill_name in self.skills:
            self.skills[skill_name].enabled = False
            self._rebuild_index()
            logger.info(f"Disabled skill: {skill_name}")
            return True
        return False

    def get_skill_stats(self) -> Dict[str, Any]:
        """Get statistics about registered skills"""
        return {
            "total_skills": len(self.skills),
            "enabled_skills": sum(1 for s in self.skills.values() if s.enabled),
            "total_executions": sum(s.execution_count for s in self.skills.values()),
        }
