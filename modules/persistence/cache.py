"""
In-Memory Cache
Fast access to frequently used data
"""

import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Cache:
    """Simple in-memory cache"""

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache

        Args:
            ttl_seconds: Time-to-live for cached items
        """
        self.data: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        logger.info(f"Cache initialized with TTL: {ttl_seconds}s")

    def set(self, key: str, value: Any) -> None:
        """
        Cache a value

        Args:
            key: Cache key
            value: Value to cache
        """
        self.data[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=self.ttl),
        }
        logger.debug(f"Cached: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get cached value

        Args:
            key: Cache key
            default: Default value if not found or expired

        Returns:
            Cached value or default
        """
        if key not in self.data:
            logger.debug(f"Cache miss: {key}")
            return default

        entry = self.data[key]

        # Check if expired
        if datetime.now() > entry["expires_at"]:
            del self.data[key]
            logger.debug(f"Cache expired: {key}")
            return default

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        if key not in self.data:
            return False

        if datetime.now() > self.data[key]["expires_at"]:
            del self.data[key]
            return False

        return True

    def delete(self, key: str) -> bool:
        """Delete cached value"""
        if key in self.data:
            del self.data[key]
            logger.debug(f"Deleted from cache: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cache"""
        self.data.clear()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        now = datetime.now()
        expired_keys = [
            k for k, v in self.data.items()
            if now > v["expires_at"]
        ]

        for key in expired_keys:
            del self.data[key]

        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self.cleanup_expired()
        return {
            "total_items": len(self.data),
            "ttl_seconds": self.ttl,
        }
