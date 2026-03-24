from __future__ import annotations

import unittest

from app.runtime.state import RunState


class RunStateTests(unittest.TestCase):
    def test_default_factories_are_independent(self) -> None:
        first = RunState(thread_id="a", user_task="task")
        second = RunState(thread_id="b", user_task="task")
        first.plan.append("x")
        self.assertEqual(second.plan, [])


if __name__ == "__main__":
    unittest.main()
