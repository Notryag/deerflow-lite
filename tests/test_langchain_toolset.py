from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.langchain_toolset import build_langchain_tools


class LangchainToolsetTests(unittest.TestCase):
    def test_build_langchain_tools_exposes_full_lead_tool_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Inspect the workspace.")

            tools = build_langchain_tools(state, workspace, Settings(), include_task=True)

            self.assertEqual(
                {tool.name for tool in tools},
                {
                    "task",
                    "search_web",
                    "read_file",
                    "write_file",
                    "list_workspace_files",
                    "run_python_code",
                },
            )

    def test_search_web_tool_updates_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Find recent updates.")
            tools = {tool.name: tool for tool in build_langchain_tools(state, workspace, Settings(), include_task=False)}

            payload = tools["search_web"].invoke({"query": "recent updates", "top_k": 2})
            results = json.loads(payload)

            self.assertTrue(state.needs_web_search)
            self.assertEqual(state.search_results, results)
            self.assertEqual(len(results), 2)

    def test_build_langchain_tools_filters_by_allowed_tool_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-tools").create()
            state = RunState(thread_id="thread-tools", user_task="Inspect the workspace.")

            tools = build_langchain_tools(
                state,
                workspace,
                Settings(),
                include_task=False,
                allowed_tool_names=("read_file", "write_file", "list_workspace_files", "run_python_code"),
            )

            self.assertEqual(
                {tool.name for tool in tools},
                {"read_file", "write_file", "list_workspace_files", "run_python_code"},
            )


if __name__ == "__main__":
    unittest.main()
