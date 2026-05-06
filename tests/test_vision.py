import unittest

from modules.vision import VisionSetup


class VisionTests(unittest.TestCase):
    def test_initialize_returns_engine(self):
        components = VisionSetup.initialize()
        self.assertIn("vision_engine", components)
        self.assertTrue(hasattr(components["vision_engine"], "is_available"))


if __name__ == "__main__":
    unittest.main()
