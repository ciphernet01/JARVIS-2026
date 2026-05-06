import unittest
from unittest.mock import Mock

from core.assistant import Assistant


class AssistantTests(unittest.TestCase):
    def test_process_input_uses_skill_registry(self):
        registry = Mock()
        registry.execute_query.return_value = "hello there"

        assistant = Assistant(skill_registry=registry)
        assistant.set_user_context("user_name", "Sir")

        response = assistant._process_input("hello")

        self.assertEqual(response, "hello there")
        registry.execute_query.assert_called_once()

    def test_status_flags(self):
        assistant = Assistant()
        status = assistant.get_status()

        self.assertIn("is_running", status)
        self.assertIn("persistence_enabled", status)
        self.assertFalse(status["is_running"])


if __name__ == "__main__":
    unittest.main()
