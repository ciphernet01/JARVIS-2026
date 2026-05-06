"""
Skill Registry Storage
Persist skill metadata and execution statistics
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SkillStore:
    """Manage skill metadata and statistics"""

    def __init__(self, db_manager):
        """
        Initialize skill store

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def register_skill(
        self,
        name: str,
        version: str = "1.0.0",
        description: Optional[str] = None,
    ) -> Optional[str]:
        """
        Register a skill

        Args:
            name: Skill name
            version: Skill version
            description: Skill description

        Returns:
            Skill ID
        """
        try:
            skill_id = str(uuid.uuid4())

            self.db.execute("""
                INSERT OR REPLACE INTO skills (id, name, version, description, enabled)
                VALUES (?, ?, ?, ?, 1)
            """, (skill_id, name, version, description))

            self.db.commit()
            logger.info(f"Skill registered: {name}")
            return skill_id

        except Exception as e:
            logger.error(f"Failed to register skill: {e}")
            return None

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get skill by name

        Args:
            name: Skill name

        Returns:
            Skill data
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM skills WHERE name = ?",
                (name,)
            )

            if not cursor:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get skill: {e}")
            return None

    def get_enabled_skills(self) -> List[Dict[str, Any]]:
        """Get all enabled skills"""
        try:
            cursor = self.db.execute("SELECT * FROM skills WHERE enabled = 1")

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get enabled skills: {e}")
            return []

    def record_execution(self, skill_name: str) -> bool:
        """
        Record skill execution

        Args:
            skill_name: Skill name

        Returns:
            True if successful
        """
        try:
            self.db.execute("""
                UPDATE skills
                SET execution_count = execution_count + 1,
                    last_executed = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (skill_name,))

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to record execution: {e}")
            return False

    def enable_skill(self, name: str) -> bool:
        """Enable a skill"""
        try:
            self.db.execute("UPDATE skills SET enabled = 1 WHERE name = ?", (name,))
            self.db.commit()
            logger.info(f"Skill enabled: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to enable skill: {e}")
            return False

    def disable_skill(self, name: str) -> bool:
        """Disable a skill"""
        try:
            self.db.execute("UPDATE skills SET enabled = 0 WHERE name = ?", (name,))
            self.db.commit()
            logger.warning(f"Skill disabled: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable skill: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get skill statistics"""
        try:
            cursor = self.db.execute("""
                SELECT
                    COUNT(*) as total_skills,
                    COUNT(CASE WHEN enabled = 1 THEN 1 END) as enabled_skills,
                    SUM(execution_count) as total_executions
                FROM skills
            """)

            if not cursor:
                return {}

            row = cursor.fetchone()
            return dict(row) if row else {}

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def get_most_used_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently used skills"""
        try:
            cursor = self.db.execute("""
                SELECT * FROM skills
                WHERE execution_count > 0
                ORDER BY execution_count DESC
                LIMIT ?
            """, (limit,))

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get most used skills: {e}")
            return []
