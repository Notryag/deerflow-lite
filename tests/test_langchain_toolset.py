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
                    "retrieve_knowledge",
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

    def test_retrieve_knowledge_tool_updates_state_from_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "docs"
            data_dir.mkdir()
            (data_dir / "notes.md").write_text(
                "DeerFlow Lite uses local retrieval for workspace-aware tasks.",
                encoding="utf-8",
            )
            workspace = Workspace(root, "thread-tools").create()
            state = RunState(
                thread_id="thread-tools",
                user_task="Retrieve local context.",
                data_dir=str(data_dir),
            )
            settings = Settings(vector_db_dir=root / "vectors")
            tools = {tool.name: tool for tool in build_langchain_tools(state, workspace, settings, include_task=False)}

            payload = tools["retrieve_knowledge"].invoke({"query": "local retrieval", "top_k": 1})
            results = json.loads(payload)

            self.assertTrue(state.needs_retrieval)
            self.assertEqual(state.retrieved_docs, results)
            self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
