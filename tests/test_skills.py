import unittest

from modules.skills import SkillRegistry
from modules.skills.base import Skill


class EchoSkill(Skill):
    def __init__(self):
        super().__init__("echo_skill", "1.0")

    @property
    def keywords(self):
        return ["echo", "repeat"]

    @property
    def description(self):
        return "Echo the incoming query"

    def execute(self, query, context=None):
        return f"echo:{query}"


class SkillRegistryTests(unittest.TestCase):
    def test_register_and_find_skill(self):
        registry = SkillRegistry()
        skill = EchoSkill()
        registry.register(skill)

        found = registry.find_skill("please echo this")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "echo_skill")

    def test_execute_query(self):
        registry = SkillRegistry()
        registry.register(EchoSkill())

        result = registry.execute_query("echo hello", {})
        self.assertEqual(result, "echo:echo hello")

    def test_disable_skill(self):
        registry = SkillRegistry()
        registry.register(EchoSkill())
        self.assertTrue(registry.disable_skill("echo_skill"))
        self.assertIsNone(registry.find_skill("echo hello"))


if __name__ == "__main__":
    unittest.main()
