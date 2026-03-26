from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.langchain_toolset import build_langchain_tools


class LangchainToolExecutionTests(unittest.TestCase):
    def test_read_file_and_list_workspace_files_tools_execute_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Write and read a file.")
            workspace.write_text("workspace/alpha.txt", "alpha")
            tools = {tool.name: tool for tool in build_langchain_tools(state, workspace, Settings(), include_task=False)}

            contents = tools["read_file"].invoke({"path": "workspace/alpha.txt"})
            payload = tools["list_workspace_files"].invoke({})
            files = json.loads(payload)

            self.assertEqual(contents, "alpha")
            self.assertIn("workspace/alpha.txt", files)

    def test_run_python_code_tool_returns_stdout_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Run python code.")
            tools = {tool.name: tool for tool in build_langchain_tools(state, workspace, Settings(), include_task=False)}

            payload = tools["run_python_code"].invoke({"code": "print('ok')", "timeout_seconds": 5})
            result = json.loads(payload)

            self.assertEqual(result["returncode"], 0)
            self.assertIn("ok", result["stdout"])
            self.assertIn("artifacts", result)

    def test_write_file_tool_returns_relative_path_and_updates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Write a file.")
            tools = {tool.name: tool for tool in build_langchain_tools(state, workspace, Settings(), include_task=False)}

            relative = tools["write_file"].invoke({"path": "workspace/beta.txt", "content": "beta"})

            self.assertEqual(relative, "workspace/beta.txt")
            self.assertIn("workspace/beta.txt", state.artifact_files)
            self.assertEqual(workspace.read_text("workspace/beta.txt"), "beta")


if __name__ == "__main__":
    unittest.main()
