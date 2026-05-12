"""
Phase 3: Voice History Manager

Tracks and retrieves voice command/response history for:
- Audit logging
- Conversation context
- User analytics
- UI display
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import threading

logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Status of voice command processing."""
    RECOGNIZED = "recognized"
    PROCESSING = "processing"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class VoiceHistoryEntry:
    """Immutable voice history entry."""
    id: str
    timestamp: str
    command_text: str
    confidence: float
    response_text: str
    status: CommandStatus
    duration_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "command": self.command_text,
            "confidence": round(self.confidence, 3),
            "response": self.response_text,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class VoiceHistoryManager:
    """
    Manages voice command/response history.
    Thread-safe with in-memory storage capability.
    Can integrate with:
    - SQLite for persistence
    - MongoDB for cloud storage
    - Elasticsearch for analytics
    """

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._history: List[VoiceHistoryEntry] = []
        self._lock = threading.RLock()
        self._entry_count = 0

    def add_entry(
        self,
        command_text: str,
        response_text: str,
        confidence: float,
        status: CommandStatus = CommandStatus.EXECUTED,
        duration_ms: int = 0,
        metadata: Optional[Dict] = None,
    ) -> VoiceHistoryEntry:
        """Add a voice history entry."""
        with self._lock:
            self._entry_count += 1
            entry = VoiceHistoryEntry(
                id=f"voice_{self._entry_count}",
                timestamp=datetime.now().isoformat(),
                command_text=command_text,
                confidence=confidence,
                response_text=response_text,
                status=status,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )

            self._history.append(entry)

            # Keep only recent entries
            if len(self._history) > self.max_entries:
                self._history = self._history[-self.max_entries :]

            logger.debug(f"[HISTORY] Added: {entry.id} - {command_text[:50]}...")
            return entry

    def get_history(
        self,
        num_entries: int = 50,
        status: Optional[CommandStatus] = None,
        last_minutes: Optional[int] = None,
    ) -> List[VoiceHistoryEntry]:
        """Retrieve history entries (snapshot)."""
        with self._lock:
            entries = self._history.copy()

        # Filter by status
        if status:
            entries = [e for e in entries if e.status == status]

        # Filter by time window
        if last_minutes:
            cutoff = datetime.now() - timedelta(minutes=last_minutes)
            entries = [
                e
                for e in entries
                if datetime.fromisoformat(e.timestamp) > cutoff
            ]

        # Return most recent
        return entries[-num_entries:] if len(entries) > num_entries else entries

    def get_recent_commands(self, num: int = 10) -> List[str]:
        """Get recent command texts for suggestions."""
        with self._lock:
            return [
                e.command_text
                for e in self._history[-num:]
                if e.status != CommandStatus.FAILED
            ]

    def get_success_rate(self, last_minutes: Optional[int] = None) -> float:
        """Calculate command success rate."""
        entries = self.get_history(num_entries=1000, last_minutes=last_minutes)
        if not entries:
            return 0.0

        successful = [
            e for e in entries if e.status in [
                CommandStatus.EXECUTED,
                CommandStatus.RECOGNIZED,
            ]
        ]
        return len(successful) / len(entries) if entries else 0.0

    def get_average_latency(self, last_minutes: Optional[int] = None) -> float:
        """Get average command processing latency in ms."""
        entries = self.get_history(num_entries=1000, last_minutes=last_minutes)
        if not entries:
            return 0.0

        return (
            sum(e.duration_ms for e in entries) / len(entries)
            if entries
            else 0.0
        )

    def get_average_confidence(
        self, last_minutes: Optional[int] = None
    ) -> float:
        """Get average speech recognition confidence."""
        entries = self.get_history(num_entries=1000, last_minutes=last_minutes)
        if not entries:
            return 0.0

        return (
            sum(e.confidence for e in entries) / len(entries)
            if entries
            else 0.0
        )

    def clear_history(self, older_than_minutes: Optional[int] = None) -> int:
        """Clear history entries. If time specified, only old entries."""
        with self._lock:
            if older_than_minutes is None:
                removed = len(self._history)
                self._history.clear()
                return removed

            cutoff = datetime.now() - timedelta(minutes=older_than_minutes)
            new_history = [
                e
                for e in self._history
                if datetime.fromisoformat(e.timestamp) > cutoff
            ]
            removed = len(self._history) - len(new_history)
            self._history = new_history
            return removed

    def export_json(self, num_entries: int = 100) -> str:
        """Export history as JSON."""
        with self._lock:
            entries = self._history[-num_entries:]

        data = {
            "exported_at": datetime.now().isoformat(),
            "entry_count": len(entries),
            "total_entries": self._entry_count,
            "entries": [e.to_dict() for e in entries],
        }
        return json.dumps(data, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        entries = self.get_history(num_entries=10000)
        recent_hour = self.get_history(num_entries=1000, last_minutes=60)

        return {
            "total_entries": self._entry_count,
            "current_entries": len(self._history),
            "success_rate_overall": round(self.get_success_rate(), 3),
            "success_rate_1h": round(
                self.get_success_rate(last_minutes=60), 3
            ),
            "avg_latency_ms": round(self.get_average_latency(), 1),
            "avg_latency_1h_ms": round(
                self.get_average_latency(last_minutes=60), 1
            ),
            "avg_confidence": round(self.get_average_confidence(), 3),
            "avg_confidence_1h": round(
                self.get_average_confidence(last_minutes=60), 3
            ),
            "failed_count": len(
                [e for e in entries if e.status == CommandStatus.FAILED]
            ),
        }

    def __len__(self) -> int:
        """Get number of entries in history."""
        with self._lock:
            return len(self._history)


# Singleton instance
_instance = None
_lock = threading.Lock()


def get_voice_history_manager() -> VoiceHistoryManager:
    """Get or create voice history manager singleton."""
    global _instance

    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = VoiceHistoryManager()

    return _instance
