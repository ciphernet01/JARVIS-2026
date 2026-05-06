"""
Conversation History Storage
Persist and retrieve conversation history
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationStore:
    """Store and retrieve conversations"""

    def __init__(self, db_manager):
        """
        Initialize conversation store

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def save_conversation(
        self,
        user_id: str,
        query: str,
        response: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        skill_used: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Save a conversation

        Args:
            user_id: User ID
            query: User query
            response: Assistant response
            intent: Recognized intent
            confidence: Confidence score
            skill_used: Skill that handled the query
            metadata: Additional metadata

        Returns:
            Conversation ID
        """
        try:
            conv_id = str(uuid.uuid4())
            metadata_json = __import__("json").dumps(metadata or {})

            self.db.execute("""
                INSERT INTO conversations (id, user_id, query, response, intent, confidence, skill_used, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (conv_id, user_id, query, response, intent, confidence, skill_used, metadata_json))

            self.db.commit()
            logger.info(f"Conversation saved: {conv_id}")
            return conv_id

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return None

    def get_user_history(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a user

        Args:
            user_id: User ID
            limit: Number of conversations to return
            offset: Offset for pagination

        Returns:
            List of conversations
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))

            if not cursor:
                return []

            conversations = []
            for row in cursor.fetchall():
                conversations.append(dict(row))

            logger.info(f"Retrieved {len(conversations)} conversations for user {user_id}")
            return conversations

        except Exception as e:
            logger.error(f"Failed to retrieve conversation history: {e}")
            return []

    def get_recent_conversations(self, user_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent conversations within timeframe

        Args:
            user_id: User ID
            hours: Number of hours to look back

        Returns:
            List of conversations
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM conversations
                WHERE user_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            """, (user_id, hours))

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to retrieve recent conversations: {e}")
            return []

    def export_conversation_history(
        self,
        user_id: str,
        format: str = "json",
    ) -> Optional[str]:
        """
        Export conversation history

        Args:
            user_id: User ID
            format: Export format ("json", "csv")

        Returns:
            Exported data as string
        """
        conversations = self.get_user_history(user_id, limit=10000)

        if format == "json":
            import json
            return json.dumps(conversations, indent=2, default=str)

        elif format == "csv":
            import csv
            import io

            if not conversations:
                return None

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=conversations[0].keys())
            writer.writeheader()
            writer.writerows(conversations)
            return output.getvalue()

        return None

    def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search conversations

        Args:
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            List of matching conversations
        """
        try:
            search_term = f"%{query}%"
            cursor = self.db.execute("""
                SELECT * FROM conversations
                WHERE user_id = ? AND (query LIKE ? OR response LIKE ?)
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, search_term, search_term, limit))

            if not cursor:
                return []

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []

    def get_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get conversation statistics

        Args:
            user_id: User ID

        Returns:
            Statistics dictionary
        """
        try:
            cursor = self.db.execute("""
                SELECT
                    COUNT(*) as total_conversations,
                    COUNT(DISTINCT DATE(timestamp)) as days_active,
                    COUNT(DISTINCT intent) as unique_intents,
                    AVG(confidence) as avg_confidence
                FROM conversations
                WHERE user_id = ?
            """, (user_id,))

            if not cursor:
                return {}

            row = cursor.fetchone()
            stats = dict(row) if row else {}

            logger.info(f"Generated statistics for user {user_id}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def clear_old_conversations(self, user_id: str, days: int = 90) -> bool:
        """
        Delete conversations older than specified days

        Args:
            user_id: User ID
            days: Number of days

        Returns:
            True if successful
        """
        try:
            cursor = self.db.execute("""
                DELETE FROM conversations
                WHERE user_id = ? AND timestamp < datetime('now', '-' || ? || ' days')
            """, (user_id, days))

            self.db.commit()
            logger.warning(f"Deleted conversations older than {days} days for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear old conversations: {e}")
            return False
