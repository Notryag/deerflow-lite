from __future__ import annotations

import unittest

from app.runtime.state import RunState


class RunStateTests(unittest.TestCase):
    def test_default_factories_are_independent(self) -> None:
        first = RunState(thread_id="a", user_task="task")
        second = RunState(thread_id="b", user_task="task")
        first.plan.append("x")
        first.subagent_tasks.append({"task_id": "task-1"})
        first.artifact_files.append("outputs/final.md")
        self.assertEqual(second.plan, [])
        self.assertEqual(second.subagent_tasks, [])
        self.assertEqual(second.artifact_files, [])

    def test_record_subagent_task_result_and_artifacts(self) -> None:
        state = RunState(thread_id="a", user_task="task")
        state.record_subagent_task(
            task_id="task-1",
            description="Summarize docs",
            subagent_type="general-purpose",
        )
        state.record_subagent_result(
            task_id="task-1",
            status="completed",
            summary="done",
            artifacts=["workspace/notes/summary.md"],
        )
        self.assertEqual(state.subagent_tasks[0]["task_id"], "task-1")
        self.assertEqual(state.subagent_results[0]["summary"], "done")
        self.assertIn("workspace/notes/summary.md", state.artifact_files)


if __name__ == "__main__":
    unittest.main()
