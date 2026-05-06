import unittest
import time

from modules.persistence.cache import Cache


class CacheTests(unittest.TestCase):
    def test_set_and_get(self):
        cache = Cache(ttl_seconds=5)
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")
        self.assertTrue(cache.has("key"))

    def test_expiry(self):
        cache = Cache(ttl_seconds=0)
        cache.set("temp", "value")
        time.sleep(0.01)
        self.assertIsNone(cache.get("temp"))
        self.assertFalse(cache.has("temp"))

    def test_cleanup(self):
        cache = Cache(ttl_seconds=0)
        cache.set("a", 1)
        time.sleep(0.01)
        removed = cache.cleanup_expired()
        self.assertGreaterEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
