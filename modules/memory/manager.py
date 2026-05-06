"""
Memory Manager
Builds short-term and long-term memory views from persistence data.
"""

import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryManager:
    """Provide conversation memory, preference recall, and summarization."""

    PREFERENCE_KEYS = ("voice_gender", "speech_rate", "language", "theme")

    STOPWORDS = {
        "the", "and", "that", "this", "with", "from", "have", "what", "when",
        "where", "how", "your", "you", "for", "are", "was", "were", "is",
        "it", "a", "an", "to", "of", "in", "on", "at", "please", "me",
        "my", "i", "we", "us", "can", "could", "would", "should", "do",
        "does", "did", "tell", "show", "set", "remind", "open", "make",
    }

    def __init__(self, persistence_components: Optional[Dict[str, Any]] = None):
        self.persistence = persistence_components or {}
        self.current_user_id: Optional[str] = None

    def set_current_user(self, user_id: Optional[str]) -> None:
        """Set the active user for memory lookups."""
        self.current_user_id = user_id

    def _conversation_store(self):
        return self.persistence.get("conversation_store")

    def _preference_store(self):
        return self.persistence.get("preference_store")

    def _resolve_user_id(self, user_id: Optional[str] = None) -> Optional[str]:
        return user_id or self.current_user_id

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9']+", (text or "").lower())
        return [token for token in tokens if token not in self.STOPWORDS and len(token) > 2]

    def _extract_topics(self, conversations: List[Dict[str, Any]], limit: int = 5) -> List[str]:
        words: List[str] = []
        for item in conversations:
            words.extend(self._tokenize(item.get("query", "")))
            words.extend(self._tokenize(item.get("response", "")))

        if not words:
            return []

        counts = Counter(words)
        return [word for word, _ in counts.most_common(limit)]

    def get_recent_context(self, user_id: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
        """Return the most recent turns in chronological order."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return []

        store = self._conversation_store()
        if not store:
            return []

        conversations = store.get_user_history(resolved_user, limit=limit)
        return list(reversed(conversations))

    def get_preferences(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Return stored preferences for the active user."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return {}

        preference_store = self._preference_store()
        if not preference_store:
            return {}

        prefs = preference_store.get_preferences(resolved_user) or {}
        return self._normalize_preferences(prefs)

    def _normalize_preferences(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten stored preference rows into a prompt-friendly dictionary."""
        normalized: Dict[str, Any] = {}

        for key in self.PREFERENCE_KEYS:
            value = prefs.get(key)
            if value not in (None, ""):
                normalized[key] = value

        settings = prefs.get("settings", {})
        if isinstance(settings, str):
            try:
                import json

                settings = json.loads(settings)
            except Exception:
                settings = {}

        if isinstance(settings, dict):
            for key, value in settings.items():
                if value not in (None, ""):
                    normalized[key] = value

        normalized["raw"] = prefs
        return normalized

    def summarize_memory(self, user_id: Optional[str] = None, limit: int = 12) -> Dict[str, Any]:
        """Summarize recent conversation and preference context."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return {
                "user_id": None,
                "summary": "No user context available.",
                "recent_topics": [],
                "recent_context": [],
                "preferences": {},
                "last_interaction": None,
                "conversation_count": 0,
            }

        store = self._conversation_store()
        if not store:
            return {
                "user_id": resolved_user,
                "summary": "Conversation storage is not available.",
                "recent_topics": [],
                "recent_context": [],
                "preferences": self.get_preferences(resolved_user),
                "last_interaction": None,
                "conversation_count": 0,
            }

        conversations = store.get_user_history(resolved_user, limit=limit)
        recent_context = list(reversed(conversations))
        topics = self._extract_topics(conversations)
        preferences = self.get_preferences(resolved_user)
        last_interaction = conversations[0] if conversations else None
        preference_summary = self._summarize_preferences(preferences)

        if topics:
            topic_text = ", ".join(topics)
            summary = f"Recent focus areas: {topic_text}."
        else:
            summary = "No strong topics detected from recent conversations yet."

        if preference_summary:
            summary = f"{summary} Preference focus: {preference_summary}."

        return {
            "user_id": resolved_user,
            "summary": summary,
            "recent_topics": topics,
            "recent_context": recent_context,
            "preferences": preferences,
            "preference_summary": preference_summary,
            "last_interaction": last_interaction,
            "conversation_count": len(conversations),
            "generated_at": datetime.now().isoformat(),
        }

    def _summarize_preferences(self, preferences: Dict[str, Any]) -> str:
        """Create a short natural-language summary of stored preferences."""
        if not preferences:
            return ""

        parts: List[str] = []
        for key in self.PREFERENCE_KEYS:
            value = preferences.get(key)
            if value not in (None, ""):
                parts.append(f"{key.replace('_', ' ')}={value}")

        for key, value in preferences.items():
            if key in self.PREFERENCE_KEYS or key == "raw":
                continue
            if value not in (None, ""):
                parts.append(f"{key.replace('_', ' ')}={value}")

        if not parts:
            return ""

        return ", ".join(parts)

    def build_context_block(self, user_id: Optional[str] = None, limit: int = 8) -> str:
        """Build a compact context block suitable for assistant prompts."""
        snapshot = self.summarize_memory(user_id=user_id, limit=limit)
        prefs = snapshot.get("preferences", {}) or {}
        preference_summary = snapshot.get("preference_summary", "")
        recent_topics = snapshot.get("recent_topics", []) or []
        last_turn = snapshot.get("last_interaction") or {}

        lines = [f"User memory summary: {snapshot.get('summary', '')}"]

        if prefs:
            if preference_summary:
                lines.append(f"Preferences: {preference_summary}")

        if recent_topics:
            lines.append(f"Recent topics: {', '.join(recent_topics)}")

        if last_turn:
            lines.append(f"Last user query: {last_turn.get('query', '')}")
            lines.append(f"Last assistant response: {last_turn.get('response', '')}")

        return "\n".join(lines).strip()

    def search_memory(self, query: str, user_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversation memory for a query."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return []

        store = self._conversation_store()
        if not store:
            return []

        return store.search_conversations(resolved_user, query, limit=limit)

    def remember_preference(self, key: str, value: Any, user_id: Optional[str] = None) -> bool:
        """Persist a single preference for the active user."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user:
            return False

        preference_store = self._preference_store()
        if not preference_store:
            return False

        settings = {key: value}
        return preference_store.set_preferences(resolved_user, settings=settings)

    def remember_preferences(self, preferences: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """Persist a group of preferences at once."""
        resolved_user = self._resolve_user_id(user_id)
        if not resolved_user or not preferences:
            return False

        preference_store = self._preference_store()
        if not preference_store:
            return False

        payload = {key: value for key, value in preferences.items() if value not in (None, "")}
        if not payload:
            return False

        known_fields = {key: payload.pop(key) for key in list(payload.keys()) if key in self.PREFERENCE_KEYS}
        return preference_store.set_preferences(resolved_user, **known_fields, settings=payload or None)

    def get_memory_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Return memory-specific summary statistics."""
        snapshot = self.summarize_memory(user_id=user_id)
        conversations = snapshot.get("conversation_count", 0)
        topics = snapshot.get("recent_topics", []) or []

        return {
            "user_id": snapshot.get("user_id"),
            "conversation_count": conversations,
            "topic_count": len(topics),
            "recent_topics": topics,
            "has_preferences": bool(snapshot.get("preferences")),
            "preference_summary": snapshot.get("preference_summary", ""),
            "summary": snapshot.get("summary"),
        }
