"""
Phase 3: Conversation Context Manager

Manages multi-turn conversation context for maintaining
coherence, user preferences, and session state.
Includes optional SQLite persistence for session recovery.
"""

import logging
import os
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    user_input: str
    assistant_response: str
    timestamp: str
    intent: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationContextManager:
    """
    Manages multi-turn conversation context.
    Maintains:
    - Turn history
    - Current session state
    - User preferences discovered during conversation
    - Topic/intent tracking
    
    Optional SQLite persistence (enable via JARVIS_PERSIST_SESSIONS env var)
    """

    def __init__(self, session_id: str, max_turns: int = 50, persist: Optional[bool] = None):
        self.session_id = session_id
        self.max_turns = max_turns
        self._turns: List[ConversationTurn] = []
        self._lock = threading.RLock()
        self.session_start = datetime.now()
        self.current_intent: Optional[str] = None
        self.user_prefs: Dict[str, Any] = {}
        
        # Optional persistence
        self.persist_enabled = persist if persist is not None else os.getenv("JARVIS_PERSIST_SESSIONS", "").lower() == "true"
        self._db_path = None
        if self.persist_enabled:
            self._db_path = Path.home() / ".jarvis" / "sessions.db"
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._load_session()  # Load if exists

    def _init_db(self) -> None:
        """Initialize SQLite database for session persistence."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TEXT,
                    preferences TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_input TEXT,
                    assistant_response TEXT,
                    timestamp TEXT,
                    intent TEXT,
                    confidence REAL,
                    metadata TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CONTEXT] DB init failed: {e}")

    def _load_session(self) -> None:
        """Load session from database if exists."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            # Load session metadata
            cursor.execute("SELECT preferences FROM sessions WHERE session_id = ?", (self.session_id,))
            row = cursor.fetchone()
            if row:
                self.user_prefs = json.loads(row[0])
            
            # Load turns
            cursor.execute("""
                SELECT user_input, assistant_response, timestamp, intent, confidence, metadata
                FROM conversation_turns
                WHERE session_id = ?
                ORDER BY id
            """, (self.session_id,))
            
            for row in cursor.fetchall():
                turn = ConversationTurn(
                    user_input=row[0],
                    assistant_response=row[1],
                    timestamp=row[2],
                    intent=row[3],
                    confidence=row[4],
                    metadata=json.loads(row[5]) if row[5] else {},
                )
                self._turns.append(turn)
            
            if self._turns:
                logger.debug(f"[CONTEXT] Loaded {len(self._turns)} turns for session {self.session_id}")
            
            conn.close()
        except Exception as e:
            logger.debug(f"[CONTEXT] Load failed (new session): {e}")

    def _save_turn(self, turn: ConversationTurn) -> None:
        """Save a single turn to database."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO conversation_turns 
                (session_id, user_input, assistant_response, timestamp, intent, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_id,
                turn.user_input,
                turn.assistant_response,
                turn.timestamp,
                turn.intent,
                turn.confidence,
                json.dumps(turn.metadata),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CONTEXT] Turn save failed: {e}")

    def save_session(self) -> None:
        """Save session metadata to database."""
        if not self.persist_enabled:
            return
        
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_id, start_time, preferences, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                self.session_id,
                self.session_start.isoformat(),
                json.dumps(self.user_prefs),
                datetime.now().isoformat(),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CONTEXT] Session save failed: {e}")

    def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        intent: Optional[str] = None,
        confidence: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> ConversationTurn:
        """Add a conversation turn to history."""
        turn = None
        with self._lock:
            turn = ConversationTurn(
                user_input=user_input,
                assistant_response=assistant_response,
                timestamp=datetime.now().isoformat(),
                intent=intent,
                confidence=confidence,
                metadata=metadata or {},
            )

            self._turns.append(turn)

            # Keep only recent turns
            if len(self._turns) > self.max_turns:
                self._turns = self._turns[-self.max_turns :]

            # Update current intent
            if intent:
                self.current_intent = intent

            logger.debug(f"[CONTEXT] Turn {len(self._turns)}: {user_input[:50]}...")

        # Save to DB outside of lock
        if self.persist_enabled and turn:
            self._save_turn(turn)
        
        return turn

    def get_turns(self, num_turns: int = 10) -> List[ConversationTurn]:
        """Get recent conversation turns (snapshot)."""
        with self._lock:
            return self._turns[-num_turns:].copy()

    def get_context_string(self, num_turns: int = 5) -> str:
        """Format conversation context for LLM."""
        turns = self.get_turns(num_turns)
        context = ""
        for turn in turns:
            context += f"User: {turn.user_input}\n"
            context += f"Assistant: {turn.assistant_response}\n\n"
        return context

    def set_preference(self, key: str, value: Any) -> None:
        """Store user preference discovered during conversation."""
        with self._lock:
            self.user_prefs[key] = value
            logger.debug(f"[CONTEXT] Pref: {key} = {value}")
        
        # Save to DB if persistence enabled
        if self.persist_enabled:
            self.save_session()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve stored user preference."""
        with self._lock:
            return self.user_prefs.get(key, default)

    def should_clarify(self, last_confidence: float) -> bool:
        """Determine if assistant should ask for clarification."""
        return last_confidence < 0.7

    def get_session_duration_minutes(self) -> int:
        """Get conversation session duration."""
        return int((datetime.now() - self.session_start).total_seconds() / 60)

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        with self._lock:
            turns = self._turns.copy()

        return {
            "session_id": self.session_id,
            "turn_count": len(turns),
            "duration_minutes": self.get_session_duration_minutes(),
            "current_intent": self.current_intent,
            "user_preferences": self.user_prefs.copy(),
            "last_turn": (
                {
                    "user": turns[-1].user_input,
                    "assistant": turns[-1].assistant_response,
                }
                if turns
                else None
            ),
        }

    def clear(self) -> None:
        """Clear conversation history (end session)."""
        with self._lock:
            self._turns.clear()
            self.current_intent = None
            self.user_prefs.clear()
            logger.info(f"[CONTEXT] Session {self.session_id} cleared")
        
        # Clear from DB if persistence enabled
        if self.persist_enabled:
            try:
                conn = sqlite3.connect(str(self._db_path))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversation_turns WHERE session_id = ?", (self.session_id,))
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (self.session_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"[CONTEXT] DB clear failed: {e}")

    def __len__(self) -> int:
        """Get number of turns."""
        with self._lock:
            return len(self._turns)


class ConversationSessionManager:
    """
    Manages multiple concurrent conversation contexts.
    One context per user session.
    """

    def __init__(self):
        self._sessions: Dict[str, ConversationContextManager] = {}
        self._lock = threading.RLock()

    def get_context(self, session_id: str) -> ConversationContextManager:
        """Get or create conversation context for session."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ConversationContextManager(
                    session_id
                )
            return self._sessions[session_id]

    def end_session(self, session_id: str) -> Dict[str, Any]:
        """End a session and return summary."""
        with self._lock:
            context = self._sessions.pop(session_id, None)

        if context:
            summary = context.get_summary()
            context.clear()
            logger.info(f"[CONTEXT] Session {session_id} ended")
            return summary

        return {}

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def __len__(self) -> int:
        """Get number of active sessions."""
        with self._lock:
            return len(self._sessions)


# Singleton instance
_instance = None
_lock = threading.Lock()


def get_session_manager() -> ConversationSessionManager:
    """Get or create session manager singleton."""
    global _instance

    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ConversationSessionManager()

    return _instance
