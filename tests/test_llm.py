import unittest
from unittest.mock import Mock, patch

from modules.llm import OllamaManager


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.manager = OllamaManager(base_url="http://localhost:11434", model="llama3.1")

    @patch("modules.llm.ollama.requests.post")
    def test_decide_action_parses_skill_plan(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {
                "content": '{"type":"skill","skill_name":"weather_skill","skill_query":"weather in london","response":"Checking that now","confidence":0.91}'
            }
        }
        mock_post.return_value = response

        plan = self.manager.decide_action(
            "what is the weather in london",
            {"available_skills": [{"name": "weather_skill", "description": "Weather"}]},
        )

        self.assertEqual(plan["type"], "skill")
        self.assertEqual(plan["skill_name"], "weather_skill")
        self.assertEqual(plan["skill_query"], "weather in london")

    @patch("modules.llm.ollama.requests.post")
    def test_refine_response_returns_model_text(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {"content": "The weather in London is clear."}}
        mock_post.return_value = response

        text = self.manager.refine_response(
            "weather?",
            "Weather in London: clear skies.",
            {"user_name": "Sir"},
        )

        self.assertEqual(text, "The weather in London is clear.")

    @patch("modules.llm.ollama.requests.post")
    def test_chat_falls_back_to_raw_text(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {"content": "Hello, Sir."}}
        mock_post.return_value = response

        text = self.manager.chat("hello")

        self.assertEqual(text, "Hello, Sir.")


if __name__ == "__main__":
    unittest.main()
