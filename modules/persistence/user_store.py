"""
User Data Models
Store and retrieve user information
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class UserStore:
    """Manage user data"""

    def __init__(self, db_manager):
        """
        Initialize user store

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def create_user(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create new user

        Args:
            username: Username
            password_hash: Hashed password
            email: Email address

        Returns:
            User ID
        """
        try:
            user_id = str(uuid.uuid4())

            self.db.execute("""
                INSERT INTO users (id, username, password_hash, email)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, password_hash, email))

            self.db.commit()
            logger.info(f"User created: {username} ({user_id})")
            return user_id

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID

        Args:
            user_id: User ID

        Returns:
            User data
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )

            if not cursor:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            cursor = self.db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )

            if not cursor:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get user by username: {e}")
            return None

    def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update user

        Args:
            user_id: User ID
            email: New email
            preferences: User preferences

        Returns:
            True if successful
        """
        try:
            prefs_json = json.dumps(preferences or {})

            self.db.execute("""
                UPDATE users
                SET email = COALESCE(?, email),
                    preferences = COALESCE(?, preferences)
                WHERE id = ?
            """, (email, prefs_json if preferences else None, user_id))

            self.db.commit()
            logger.info(f"User updated: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Delete user (GDPR)

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            # Delete related data first
            self.db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            self.db.execute("DELETE FROM preferences WHERE user_id = ?", (user_id,))
            self.db.execute("DELETE FROM audit_log WHERE user_id = ?", (user_id,))
            self.db.execute("DELETE FROM scheduled_tasks WHERE user_id = ?", (user_id,))
            self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))

            self.db.commit()
            logger.warning(f"User deleted (GDPR): {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False

    def user_exists(self, username: str) -> bool:
        """Check if username exists"""
        try:
            cursor = self.db.execute(
                "SELECT 1 FROM users WHERE username = ? LIMIT 1",
                (username,)
            )
            return cursor and cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check user existence: {e}")
            return False


class PreferenceStore:
    """Manage user preferences"""

    def __init__(self, db_manager):
        """
        Initialize preference store

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def set_preferences(
        self,
        user_id: str,
        voice_gender: Optional[str] = None,
        speech_rate: Optional[int] = None,
        language: Optional[str] = None,
        theme: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Set user preferences

        Args:
            user_id: User ID
            voice_gender: Voice gender ("male", "female")
            speech_rate: Speech rate (50-200)
            language: Language code
            theme: UI theme
            settings: Additional settings

        Returns:
            True if successful
        """
        try:
            pref_id = str(uuid.uuid4())
            settings_json = json.dumps(settings or {})

            # Try update first
            cursor = self.db.execute(
                "SELECT id FROM preferences WHERE user_id = ?",
                (user_id,)
            )

            if cursor and cursor.fetchone():
                self.db.execute("""
                    UPDATE preferences
                    SET voice_gender = COALESCE(?, voice_gender),
                        speech_rate = COALESCE(?, speech_rate),
                        language = COALESCE(?, language),
                        theme = COALESCE(?, theme),
                        settings = COALESCE(?, settings)
                    WHERE user_id = ?
                """, (voice_gender, speech_rate, language, theme, settings_json, user_id))
            else:
                self.db.execute("""
                    INSERT INTO preferences (id, user_id, voice_gender, speech_rate, language, theme, settings)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pref_id, user_id, voice_gender, speech_rate, language, theme, settings_json))

            self.db.commit()
            logger.info(f"Preferences saved for user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to set preferences: {e}")
            return False

    def get_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user preferences

        Args:
            user_id: User ID

        Returns:
            Preferences data
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM preferences WHERE user_id = ?",
                (user_id,)
            )

            if not cursor:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return None

    def get_setting(self, user_id: str, key: str, default: Any = None) -> Any:
        """
        Get a specific setting

        Args:
            user_id: User ID
            key: Setting key
            default: Default value

        Returns:
            Setting value
        """
        prefs = self.get_preferences(user_id)
        if not prefs:
            return default

        settings = prefs.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)

        return settings.get(key, default)

    def set_setting(self, user_id: str, key: str, value: Any) -> bool:
        """
        Set a specific setting

        Args:
            user_id: User ID
            key: Setting key
            value: Setting value

        Returns:
            True if successful
        """
        prefs = self.get_preferences(user_id)
        settings = {}

        if prefs:
            settings_str = prefs.get("settings", "{}")
            settings = json.loads(settings_str) if isinstance(settings_str, str) else settings_str

        settings[key] = value
        return self.set_preferences(user_id, settings=settings)
