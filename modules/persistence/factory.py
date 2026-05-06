"""
Persistence Factory
Manage persistence layer initialization and connections
"""

import logging
from typing import Dict, Any, Optional
from .database import DatabaseManager
from .conversation_store import ConversationStore
from .audit_log import AuditLogger
from .cache import Cache
from .user_store import UserStore, PreferenceStore
from .skill_store import SkillStore
from .task_store import TaskStore

logger = logging.getLogger(__name__)


class PersistenceFactory:
    """Factory for managing persistence layer"""

    @staticmethod
    def initialize(db_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Initialize persistence layer

        Args:
            db_url: Database URL
                - SQLite: sqlite:///path/to/db.db
                - PostgreSQL: postgresql://user:pass@host/dbname
                - MySQL: mysql://user:pass@host/dbname

        Returns:
            Dictionary of persistence components
        """
        try:
            # Initialize database
            db_manager = DatabaseManager(db_url)
            if not db_manager.connect():
                raise Exception("Failed to connect to database")

            if not db_manager.create_tables():
                raise Exception("Failed to create database tables")

            # Initialize stores
            conversation_store = ConversationStore(db_manager)
            audit_logger = AuditLogger(db_manager)
            user_store = UserStore(db_manager)
            preference_store = PreferenceStore(db_manager)
            skill_store = SkillStore(db_manager)
            task_store = TaskStore(db_manager)

            # Initialize cache
            cache = Cache(ttl_seconds=300)

            logger.info("Persistence layer initialized successfully")

            return {
                "db_manager": db_manager,
                "conversation_store": conversation_store,
                "audit_logger": audit_logger,
                "user_store": user_store,
                "preference_store": preference_store,
                "skill_store": skill_store,
                "task_store": task_store,
                "cache": cache,
            }

        except Exception as e:
            logger.error(f"Failed to initialize persistence layer: {e}")
            raise

    @staticmethod
    def shutdown(persistence_components: Dict[str, Any]) -> None:
        """
        Shutdown persistence layer

        Args:
            persistence_components: Dictionary from initialize()
        """
        try:
            db_manager = persistence_components.get("db_manager")
            if db_manager:
                db_manager.disconnect()

            cache = persistence_components.get("cache")
            if cache:
                cache.clear()

            logger.info("Persistence layer shutdown complete")

        except Exception as e:
            logger.error(f"Error during persistence shutdown: {e}")
