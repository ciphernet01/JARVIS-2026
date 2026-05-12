import unittest

from modules.services import DeviceManager


class DeviceManagerTests(unittest.TestCase):
    def test_snapshot_contains_core_fields(self):
        manager = DeviceManager(workspace_root="c:/JARVIS-2026")
        snapshot = manager.snapshot()

        self.assertIn("platform", snapshot)
        self.assertIn("cpu_cores", snapshot)
        self.assertIn("memory_total_gb", snapshot)
        self.assertIn("camera_available", snapshot)
        self.assertIn("microphone_available", snapshot)
        self.assertIn("tts_available", snapshot)

    def test_capability_matrix_is_structured(self):
        manager = DeviceManager(workspace_root="c:/JARVIS-2026")
        matrix = manager.capability_matrix()

        self.assertIn("camera", matrix)
        self.assertIn("display", matrix)
        self.assertIn("battery", matrix)
        self.assertIn("network", matrix)


if __name__ == "__main__":
    unittest.main()
