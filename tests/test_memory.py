import unittest

from core.assistant import Assistant
from modules.memory import MemoryManager
from modules.persistence import PersistenceFactory


class DummySkillRegistry:
    def __init__(self):
        self.skills = {}

    def execute_query(self, user_input, user_context):
        return f"Handled: {user_input}"


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.persistence = PersistenceFactory.initialize("sqlite:///:memory:")
        self.memory = MemoryManager(self.persistence)
        self.memory.set_current_user("default_user")

    def tearDown(self):
        PersistenceFactory.shutdown(self.persistence)

    def test_memory_summary_extracts_topics(self):
        store = self.persistence["conversation_store"]
        store.save_conversation("default_user", "set a reminder for tomorrow", "Reminder created", skill_used="reminder")
        store.save_conversation("default_user", "what is the weather in london", "It is rainy", skill_used="weather")

        summary = self.memory.summarize_memory(limit=10)

        self.assertEqual(summary["user_id"], "default_user")
        self.assertGreaterEqual(summary["conversation_count"], 2)
        self.assertIn("weather", summary["summary"].lower())

    def test_assistant_exposes_memory_summary(self):
        assistant = Assistant(
            skill_registry=DummySkillRegistry(),
            persistence_components=self.persistence,
        )
        assistant.set_current_user("default_user")

        assistant._process_input("remember that I like concise replies")

        status = assistant.get_status()
        memory = assistant.get_memory_summary()

        self.assertTrue(status["memory_enabled"])
        self.assertIsNotNone(memory)
        self.assertEqual(memory["user_id"], "default_user")

    def test_preference_memory_is_normalized_and_recalled(self):
        preference_store = self.persistence["preference_store"]
        preference_store.set_preferences(
            "default_user",
            voice_gender="female",
            speech_rate=145,
            language="en-US",
            theme="classic",
            settings={"wake_word": "jarvis", "voice_style": "calm"},
        )

        prefs = self.memory.get_preferences()
        self.assertEqual(prefs["voice_gender"], "female")
        self.assertEqual(prefs["wake_word"], "jarvis")

        context = self.memory.build_context_block()
        self.assertIn("voice gender=female", context.lower())
        self.assertIn("wake word=jarvis", context.lower())

        assistant = Assistant(
            skill_registry=DummySkillRegistry(),
            persistence_components=self.persistence,
        )
        assistant.set_current_user("default_user")
        self.assertTrue(assistant.remember_user_preference("theme", "neon"))
        updated_prefs = assistant.get_memory_summary()
        self.assertIn("theme=neon", updated_prefs["summary"].lower())


if __name__ == "__main__":
    unittest.main()