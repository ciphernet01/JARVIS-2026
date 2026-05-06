import unittest
from unittest.mock import Mock, patch

from core.config import ConfigManager
from modules.llm import create_llm_manager, GeminiManager, CompositeLLMManager


class LLMFactoryTests(unittest.TestCase):
    @patch("modules.llm.factory.GeminiManager")
    def test_factory_uses_gemini_only(self, mock_gemini_cls):
        config = ConfigManager()
        config.llm.provider = "gemini"
        config.llm.enabled = True
        config.llm.model = "gemini-2.5-flash"

        gemini = Mock(spec=GeminiManager)
        gemini.is_available.return_value = True
        mock_gemini_cls.return_value = gemini

        manager = create_llm_manager(config)

        self.assertIsInstance(manager, CompositeLLMManager)
        self.assertIs(manager.primary, gemini)
        self.assertIsNone(manager.fallback)


if __name__ == "__main__":
    unittest.main()