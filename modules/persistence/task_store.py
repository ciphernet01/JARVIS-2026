"""
Task Scheduler Storage
Store and manage scheduled tasks
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStore:
    """Manage scheduled tasks"""

    def __init__(self, db_manager):
        """
        Initialize task store

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def create_task(
        self,
        user_id: str,
        task_name: str,
        schedule: str,
        status: str = "pending",
    ) -> Optional[str]:
        """
        Create scheduled task

        Args:
            user_id: User ID
            task_name: Task name
            schedule: Cron schedule
            status: Task status

        Returns:
            Task ID
        """
        try:
            task_id = str(uuid.uuid4())

            self.db.execute("""
                INSERT INTO scheduled_tasks (id, user_id, task_name, schedule, status)
                VALUES (?, ?, ?, ?, ?)
            """, (task_id, user_id, task_name, schedule, status))

            self.db.commit()
            logger.info(f"Task created: {task_name} ({task_id})")
            return task_id

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        try:
            cursor = self.db.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?",
                (task_id,)
            )

            if not cursor:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None

    def get_user_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a user"""
        try:
            cursor = self.db.execute(
                "SELECT * FROM scheduled_tasks WHERE user_id = ?",
                (user_id,)
            )

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get user tasks: {e}")
            return []

    def update_task_status(
        self,
        task_id: str,
        status: str,
        next_execution: Optional[str] = None,
    ) -> bool:
        """Update task status"""
        try:
            self.db.execute("""
                UPDATE scheduled_tasks
                SET status = ?,
                    last_executed = CURRENT_TIMESTAMP,
                    next_execution = ?
                WHERE id = ?
            """, (status, next_execution, task_id))

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return False

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks ready to execute"""
        try:
            cursor = self.db.execute("""
                SELECT * FROM scheduled_tasks
                WHERE status = 'pending' OR (status = 'scheduled' AND next_execution <= CURRENT_TIMESTAMP)
            """)

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []

    def delete_task(self, task_id: str) -> bool:
        """Delete task"""
        try:
            self.db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            self.db.commit()
            logger.info(f"Task deleted: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
