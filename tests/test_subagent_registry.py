from __future__ import annotations

import unittest

from app.subagents.registry import SubagentRegistry


class SubagentRegistryTests(unittest.TestCase):
    def test_registry_returns_builtin_general_purpose_spec(self) -> None:
        registry = SubagentRegistry()
        spec = registry.get("general-purpose")
        self.assertEqual(spec.name, "general-purpose")
        self.assertEqual(spec.max_turns, 8)
        self.assertIn("retrieve_knowledge", spec.allowed_tools)
        self.assertIn("task", spec.disallowed_tools)

    def test_registry_rejects_unknown_subagent_type(self) -> None:
        registry = SubagentRegistry()
        with self.assertRaises(ValueError):
            registry.get("unknown")

    def test_registry_validates_max_turns_against_type_limit(self) -> None:
        registry = SubagentRegistry()
        self.assertEqual(registry.resolve_max_turns("general-purpose", None), 8)
        self.assertEqual(registry.resolve_max_turns("bash", 4), 4)
        with self.assertRaises(ValueError):
            registry.resolve_max_turns("bash", 99)


if __name__ == "__main__":
    unittest.main()
