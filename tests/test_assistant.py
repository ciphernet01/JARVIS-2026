import os
import tempfile
import unittest
from unittest.mock import Mock

from core.assistant import Assistant
from modules.persistence import PersistenceFactory


class AssistantTests(unittest.TestCase):
    def test_process_input_uses_skill_registry(self):
        registry = Mock()
        registry.execute_query.return_value = "hello there"

        assistant = Assistant(skill_registry=registry)
        assistant.react_agent = None
        assistant.llm_router = None
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

    def test_project_index_is_in_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = os.path.join(temp_dir, "workspace")
            os.makedirs(workspace_root, exist_ok=True)

            with open(os.path.join(workspace_root, "README.md"), "w", encoding="utf-8") as handle:
                handle.write("# Temp Project\n\nDemo workspace.")

            with open(os.path.join(workspace_root, "package.json"), "w", encoding="utf-8") as handle:
                handle.write('{"name":"temp-project","dependencies":{"react":"18.0.0"}}')

            previous_workspace = os.environ.get("JARVIS_WORKSPACE")
            os.environ["JARVIS_WORKSPACE"] = workspace_root
            persistence = PersistenceFactory.initialize("sqlite:///:memory:")

            try:
                assistant = Assistant(persistence_components=persistence)
                assistant.set_current_user("default_user")

                context = assistant._build_llm_context("what projects are available")

                self.assertIn("project_index", context)
                self.assertGreaterEqual(context["project_index"].get("project_count", 0), 1)
                self.assertIn("Temp Project", context["project_index"].get("summary", ""))
            finally:
                PersistenceFactory.shutdown(persistence)
                if previous_workspace is None:
                    os.environ.pop("JARVIS_WORKSPACE", None)
                else:
                    os.environ["JARVIS_WORKSPACE"] = previous_workspace


if __name__ == "__main__":
    unittest.main()
