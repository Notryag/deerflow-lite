from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.executor import SubagentExecutor
from app.tools.task_tool import TaskTool


class SubagentExecutorTests(unittest.TestCase):
    def test_execute_task_completes_task_and_writes_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-exec").create()
            state = RunState(thread_id="thread-exec", user_task="delegate this task")
            tool = TaskTool(state, workspace)
            task = tool.create_task(
                description="Inspect workspace files",
                prompt="List the relevant files and summarize what you find.",
            )

            result = SubagentExecutor(Settings()).execute_task(state, workspace, task["task_id"])

            self.assertEqual(result["status"], "completed")
            self.assertEqual(state.subagent_tasks[0]["status"], "completed")
            self.assertEqual(state.subagent_results[0]["task_id"], task["task_id"])
            self.assertIn("subagents/task_001/result.md", state.artifact_files)
            self.assertTrue((workspace.thread_dir / "subagents" / "task_001" / "result.md").exists())


if __name__ == "__main__":
    unittest.main()
