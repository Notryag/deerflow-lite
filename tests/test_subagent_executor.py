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

    def test_execute_tasks_rejects_batch_larger_than_configured_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-batch").create()
            state = RunState(thread_id="thread-batch", user_task="delegate this task")
            tool = TaskTool(state, workspace)
            first = tool.create_task(description="Task one", prompt="Do one thing.")
            second = tool.create_task(description="Task two", prompt="Do another thing.")
            executor = SubagentExecutor(Settings(subagent_max_concurrency=1))

            with self.assertRaises(ValueError):
                executor.execute_tasks(state, workspace, [first["task_id"], second["task_id"]])

    def test_execute_task_rejects_nested_delegation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-nested").create()
            state = RunState(thread_id="thread-nested", user_task="delegate this task")
            tool = TaskTool(state, workspace)
            task = tool.create_task(description="Inspect workspace files", prompt="List files.")
            state.subagent_tasks[0]["allowed_tools"] = ["task"]
            state.subagent_tasks[0]["disallowed_tools"] = []

            with self.assertRaises(ValueError):
                SubagentExecutor(Settings()).execute_task(state, workspace, task["task_id"])


if __name__ == "__main__":
    unittest.main()
