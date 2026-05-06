import tempfile
import unittest
from pathlib import Path

from modules.multimodal import MultimodalManager
from modules.persistence import PersistenceFactory
from modules.vision import VisionSetup


class MultimodalTests(unittest.TestCase):
    def setUp(self):
        self.persistence = PersistenceFactory.initialize("sqlite:///:memory:")
        self.manager = MultimodalManager(VisionSetup.initialize()["vision_engine"])

    def tearDown(self):
        PersistenceFactory.shutdown(self.persistence)

    def test_analyze_text_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("Jarvis should remember context and provide proactive briefings.", encoding="utf-8")

            result = self.manager.analyze_file(str(path))

            self.assertTrue(result["success"])
            self.assertEqual(result["analysis_type"], "text")
            self.assertIn("jarvis", result["preview"].lower())
            self.assertGreater(result["word_count"], 3)

    def test_summarize_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "a.txt").write_text("alpha", encoding="utf-8")
            (base / "b.md").write_text("beta", encoding="utf-8")

            result = self.manager.summarize_folder(str(base))

            self.assertTrue(result["success"])
            self.assertEqual(result["analysis_type"], "folder")
            self.assertEqual(result["file_count"], 2)
            self.assertIn(".txt", result["file_type_counts"])

    def test_build_multimodal_brief(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.md"
            path.write_text("Morning briefing: tasks, weather, and memory recall.", encoding="utf-8")

            result = self.manager.build_multimodal_brief(str(path))

            self.assertTrue(result["success"])
            self.assertIn("report.md", result["summary"])
            self.assertIn("topics", result["summary"].lower())


if __name__ == "__main__":
    unittest.main()
