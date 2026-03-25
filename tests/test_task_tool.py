from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.task_tool import TaskTool


class TaskToolTests(unittest.TestCase):
    def test_create_task_records_state_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-task").create()
            state = RunState(thread_id="thread-task", user_task="delegate")
            tool = TaskTool(state, workspace)

            result = tool.create_task(
                description="Inspect docs",
                prompt="Read the shared workspace and summarize the findings.",
            )

            self.assertEqual(result["task_id"], "task_001")
            self.assertEqual(result["status"], "pending")
            self.assertEqual(state.subagent_tasks[0]["subagent_type"], "general-purpose")
            manifest = workspace.load_manifest()
            self.assertEqual(manifest["tasks"][0]["task_id"], "task_001")

    def test_create_task_rejects_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-invalid").create()
            state = RunState(thread_id="thread-invalid", user_task="delegate")
            tool = TaskTool(state, workspace)

            with self.assertRaises(ValueError):
                tool.create_task(description="", prompt="x")
            with self.assertRaises(ValueError):
                tool.create_task(description="x", prompt="")
            with self.assertRaises(ValueError):
                tool.create_task(description="x", prompt="y", subagent_type="missing")
            with self.assertRaises(ValueError):
                tool.create_task(description="x", prompt="y", max_turns=0)


if __name__ == "__main__":
    unittest.main()
