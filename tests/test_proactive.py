import unittest

from core.assistant import Assistant
from modules.memory import MemoryManager
from modules.persistence import PersistenceFactory
from modules.proactive import ProactiveManager


class DummySkillRegistry:
    def __init__(self):
        self.skills = {}

    def execute_query(self, user_input, user_context):
        return f"Handled: {user_input}"


class ProactiveTests(unittest.TestCase):
    def setUp(self):
        self.persistence = PersistenceFactory.initialize("sqlite:///:memory:")
        self.assistant = Assistant(
            skill_registry=DummySkillRegistry(),
            persistence_components=self.persistence,
        )
        self.assistant.set_current_user("default_user")
        self.assistant.set_user_context("user_name", "Sir")
        self.assistant.memory = MemoryManager(self.persistence)
        self.assistant.memory.set_current_user("default_user")

        self.task_store = self.persistence["task_store"]
        self.task_store.create_task("default_user", "Review calendar", "daily", status="pending")
        self.task_store.create_task("default_user", "Prepare report", "tomorrow 09:00", status="scheduled")

        store = self.persistence["conversation_store"]
        store.save_conversation("default_user", "set a reminder to call mom", "Done", skill_used="reminder")
        store.save_conversation("default_user", "what is the weather today", "Sunny", skill_used="weather")

        self.manager = ProactiveManager(self.assistant, self.persistence)

    def tearDown(self):
        PersistenceFactory.shutdown(self.persistence)

    def test_briefing_includes_tasks_and_memory(self):
        briefing = self.manager.build_briefing(
            user_id="default_user",
            system_metrics={"cpu": {"percent": 12}, "memory": {"percent": 34}, "disk": {"percent": 40}},
            weather={"location": "London", "temp_c": "18", "description": "clear skies"},
        )

        self.assertEqual(briefing["user_id"], "default_user")
        self.assertIn("Good day", briefing["summary"])
        self.assertTrue(briefing["upcoming_tasks"])
        self.assertTrue(briefing["memory"])
        self.assertIn("Recent focus", briefing["summary"])

    def test_alerts_include_tasks(self):
        alerts = self.manager.build_alerts(user_id="default_user", system_metrics={"cpu": {"percent": 95}})

        kinds = {alert["type"] for alert in alerts}
        self.assertIn("task", kinds)
        self.assertIn("system", kinds)

    def test_briefing_text_is_readable(self):
        text = self.manager.build_briefing_text(user_id="default_user")
        self.assertIn("Good day", text)
        self.assertIn("tasks", text.lower())


if __name__ == "__main__":
    unittest.main()
