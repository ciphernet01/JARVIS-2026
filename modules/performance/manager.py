"""
Performance Manager
Centralized caching for expensive API responses and computed metrics
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from modules.persistence.cache import Cache

logger = logging.getLogger(__name__)


class PerformanceManager:
    """Cache expensive or frequently requested values"""

    def __init__(self, ttl_seconds: int = 3):
        self.cache = Cache(ttl_seconds=ttl_seconds)
        logger.info(f"Performance manager initialized with TTL={ttl_seconds}s")

    def get(self, key: str, fallback=None):
        return self.cache.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        self.cache.set(key, value)

    def remember(self, key: str, value_factory, ttl_seconds: Optional[int] = None):
        """Get a cached item or compute and store it"""
        if self.cache.has(key):
            return self.cache.get(key)
        value = value_factory()
        if ttl_seconds and ttl_seconds != self.cache.ttl:
            original = self.cache.ttl
            self.cache.ttl = ttl_seconds
            self.cache.set(key, value)
            self.cache.ttl = original
        else:
            self.cache.set(key, value)
        return value

    def stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()

    def clear(self) -> None:
        self.cache.clear()
