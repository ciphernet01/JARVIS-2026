"""
Long-term memory for JARVIS
SQLite-backed store with Ollama embeddings for semantic search.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    Persistent memory with vector embeddings.
    Stores facts, preferences, and conversation summaries.
    Semantic search uses Ollama nomic-embed-text.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        llm_router: Optional[LLMRouter] = None,
    ):
        workspace = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace"))
        workspace.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(workspace / "long_term_memory.db")
        self.llm_router = llm_router
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    category TEXT,
                    content TEXT NOT NULL,
                    embedding TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)
                """
            )
            conn.commit()

    async def _embed(self, text: str) -> List[float]:
        if self.llm_router is None:
            logger.warning("No LLM router available for embeddings")
            return []
        try:
            return await self.llm_router.embed(text)
        except Exception as exc:
            logger.warning(f"Embedding failed: {exc}")
            return []

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def store(
        self,
        content: str,
        user_id: Optional[str] = None,
        category: str = "general",
    ) -> bool:
        """Store a memory with embedding."""
        try:
            embedding = await self._embed(content)
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO memories (user_id, category, content, embedding, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        category,
                        content,
                        json.dumps(embedding) if embedding else None,
                        now,
                        now,
                    ),
                )
                conn.commit()
            logger.info(f"Stored memory: {content[:60]}...")
            return True
        except Exception as exc:
            logger.error(f"Failed to store memory: {exc}")
            return False

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over memories using embeddings."""
        try:
            query_embedding = await self._embed(query)
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if user_id and category:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE user_id = ? AND category = ? ORDER BY id DESC",
                        (user_id, category),
                    ).fetchall()
                elif user_id:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE user_id = ? ORDER BY id DESC",
                        (user_id,),
                    ).fetchall()
                elif category:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE category = ? ORDER BY id DESC",
                        (category,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM memories ORDER BY id DESC"
                    ).fetchall()

            scored: List[tuple] = []
            for row in rows:
                row_dict = dict(row)
                emb_str = row_dict.get("embedding")
                if emb_str and query_embedding:
                    emb = json.loads(emb_str)
                    score = self._cosine_similarity(query_embedding, emb)
                else:
                    # Fallback to substring match if no embeddings
                    score = 1.0 if query.lower() in row_dict["content"].lower() else 0.0
                scored.append((score, row_dict))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = [r for _, r in scored[:limit]]
            return results
        except Exception as exc:
            logger.error(f"Memory search failed: {exc}")
            return []

    def get_recent(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent memories without semantic search."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if user_id and category:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE user_id = ? AND category = ? ORDER BY created_at DESC LIMIT ?",
                        (user_id, category, limit),
                    ).fetchall()
                elif user_id:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                        (user_id, limit),
                    ).fetchall()
                elif category:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                        (category, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.error(f"Failed to get recent memories: {exc}")
            return []

    def delete(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Failed to delete memory: {exc}")
            return False
