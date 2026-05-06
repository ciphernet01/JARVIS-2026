import unittest
from unittest.mock import Mock

from modules.agent import AgentManager


class DummySkillRegistry:
    def __init__(self):
        self.skills = {}

    def execute_skill(self, skill_name, query, context=None):
        return f"{skill_name}:{query}"

    def execute_query(self, query, context=None):
        return f"query:{query}"

    def list_skills(self):
        return [{"name": "weather_skill", "description": "Weather"}]


class AgentTests(unittest.TestCase):
    def test_should_plan_detects_complex_requests(self):
        agent = AgentManager(llm_manager=None, skill_registry=DummySkillRegistry())
        self.assertTrue(agent.should_plan("set a reminder then check the weather"))
        self.assertFalse(agent.should_plan("what time is it"))

    def test_execute_plan_runs_skills(self):
        llm = Mock()
        llm.refine_response.return_value = "Done"
        agent = AgentManager(llm_manager=llm, skill_registry=DummySkillRegistry(), persistence_components={})

        plan = {
            "summary": "Do two steps",
            "steps": [
                {"id": "1", "type": "skill", "title": "Weather", "skill_name": "weather_skill", "input": "weather in london"},
                {"id": "2", "type": "chat", "title": "Wrap up", "input": "Summarize the result"},
            ],
        }

        result = agent.execute_plan(plan, "check weather then summarize", {"user_id": "default_user"})

        self.assertEqual(result["type"], "workflow_result")
        self.assertEqual(len(result["steps"]), 2)
        self.assertIn("Done", result["summary"])


if __name__ == "__main__":
    unittest.main()
