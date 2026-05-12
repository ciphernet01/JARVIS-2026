"""
Database Connection Manager
Handles database connections and migrations
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
import sqlite3
import json
from datetime import datetime
from threading import RLock

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage database connections"""

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_url: Database URL
            - SQLite: sqlite:///path/to/db.db
            - PostgreSQL: postgresql://user:pass@host/dbname
            - MySQL: mysql://user:pass@host/dbname
        """
        self.db_url = db_url or "sqlite:///:memory:"
        self.db_type = self._parse_db_type(db_url)
        self.connection = None
        self.initialized = False
        self._lock = RLock()

        logger.info(f"Database manager initialized with {self.db_type}")

    def _parse_db_type(self, url: Optional[str]) -> str:
        """Parse database type from URL"""
        if not url:
            return "sqlite"
        if url.startswith("postgresql://"):
            return "postgresql"
        elif url.startswith("mysql://"):
            return "mysql"
        elif url.startswith("sqlite://"):
            return "sqlite"
        else:
            return "unknown"

    def connect(self) -> bool:
        """Connect to database"""
        try:
            if self.db_type == "sqlite":
                # Extract path from URL
                if self.db_url == "sqlite:///:memory:":
                    path = ":memory:"
                else:
                    path = self.db_url.replace("sqlite:///", "")

                self.connection = sqlite3.connect(path, check_same_thread=False)
                self.connection.row_factory = sqlite3.Row
                logger.info(f"Connected to SQLite: {path}")
            else:
                logger.error(f"Database type {self.db_type} not yet supported")
                return False

            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from database"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from database")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {e}")

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query"""
        if not self.connection:
            logger.error("Not connected to database")
            return None

        try:
            with self._lock:
                cursor = self.connection.cursor()
                cursor.execute(query, params)
                return cursor
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None

    def commit(self) -> bool:
        """Commit transaction"""
        try:
            with self._lock:
                self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            return False

    def create_tables(self) -> bool:
        """Create essential database tables"""
        try:
            # Users table
            self.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    preferences TEXT
                )
            """)

            # Conversations table
            self.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    query TEXT NOT NULL,
                    response TEXT,
                    intent TEXT,
                    confidence REAL,
                    skill_used TEXT,
                    metadata TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Skills table
            self.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    version TEXT,
                    description TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    execution_count INTEGER DEFAULT 0,
                    last_executed TIMESTAMP
                )
            """)

            # User preferences table
            self.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id TEXT PRIMARY KEY,
                    user_id TEXT UNIQUE NOT NULL,
                    voice_gender TEXT,
                    speech_rate INTEGER,
                    language TEXT,
                    theme TEXT,
                    settings TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Audit log table
            self.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    success BOOLEAN,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Scheduled tasks table
            self.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    schedule TEXT,
                    last_executed TIMESTAMP,
                    next_execution TIMESTAMP,
                    status TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Project index table
            self.execute("""
                CREATE TABLE IF NOT EXISTS project_index (
                    id TEXT PRIMARY KEY,
                    workspace_root TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    project_type TEXT,
                    summary TEXT,
                    source_file TEXT,
                    metadata TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(workspace_root, root_path)
                )
            """)

            # Create indices for performance
            self.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_project_index_workspace_root ON project_index(workspace_root)")
            self.execute("CREATE INDEX IF NOT EXISTS idx_project_index_project_type ON project_index(project_type)")

            self.commit()
            logger.info("Database tables created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
