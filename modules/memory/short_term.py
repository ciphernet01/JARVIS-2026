"""
Short-term memory for JARVIS
Conversation buffer holding the last N turns.
"""

import json
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationBuffer:
    """Ring buffer of recent conversation turns."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._buffer: deque[Dict[str, Any]] = deque(maxlen=max_turns)

    def add(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a conversation turn."""
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            turn["metadata"] = metadata
        self._buffer.append(turn)
        logger.debug(f"Buffer added {role} turn ({len(self._buffer)}/{self.max_turns})")

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Return turns as OpenAI-style message dicts."""
        turns = list(self._buffer)
        if limit:
            turns = turns[-limit:]
        return [{"role": t["role"], "content": t["content"]} for t in turns]

    def get_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return raw turn data including metadata."""
        turns = list(self._buffer)
        if limit:
            turns = turns[-limit:]
        return turns

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        logger.info("Conversation buffer cleared")

    def to_json(self) -> str:
        """Serialize buffer to JSON."""
        return json.dumps(list(self._buffer), default=str)

    @classmethod
    def from_json(cls, data: str, max_turns: int = 20) -> "ConversationBuffer":
        """Restore buffer from JSON."""
        buf = cls(max_turns=max_turns)
        turns = json.loads(data)
        for t in turns[-max_turns:]:
            buf._buffer.append(t)
        return buf
