from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config.settings import Settings
from app.workflows.run_task import run_task


class WorkflowTests(unittest.TestCase):
    def test_run_task_allows_lead_agent_direct_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                runtime_dir=root / "runtime",
                use_stub_agents=True,
            )
            state = run_task(
                user_task="Say hello in one sentence.",
                thread_id="thread-direct",
                settings=settings,
            )

            workspace = Path(state.workspace_dir or "")
            self.assertEqual(state.status, "completed")
            self.assertEqual(state.task_type, "direct_response")
            self.assertTrue((workspace / "outputs" / "final.md").exists())
            self.assertTrue((workspace / "subagents" / "manifest.json").exists())
            self.assertFalse((workspace / "notes" / "research.md").exists())
            self.assertEqual(state.notes_files, [])
            self.assertIn("outputs/final.md", state.artifact_files)
            self.assertTrue(bool(state.final_answer))

    def test_run_task_allows_lead_agent_delegation_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                runtime_dir=root / "runtime",
                use_stub_agents=True,
            )
            state = run_task(
                user_task="Delegate this task and inspect the workspace before answering.",
                thread_id="thread-delegate",
                settings=settings,
            )

            workspace = Path(state.workspace_dir or "")
            self.assertEqual(state.status, "completed")
            self.assertEqual(state.task_type, "delegated_response")
            self.assertEqual(len(state.subagent_tasks), 1)
            self.assertEqual(len(state.subagent_results), 1)
            self.assertTrue((workspace / "subagents" / "task_001" / "result.md").exists())
            self.assertTrue((workspace / "outputs" / "final.md").exists())
            self.assertTrue((workspace / "notes" / "research.md").exists())
            self.assertIn("subagents/task_001/result.md", state.artifact_files)
            self.assertIn("notes/research.md", state.artifact_files)
            self.assertTrue(bool(state.final_answer))

    def test_run_task_creates_workspace_notes_and_final_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "docs"
            data_dir.mkdir()
            (data_dir / "notes.md").write_text(
                "DeerFlow Lite uses explicit orchestration, retrieval, and markdown outputs.",
                encoding="utf-8",
            )

            settings = Settings(
                runtime_dir=root / "runtime",
                use_stub_agents=True,
            )
            state = run_task(
                user_task="Summarize the docs directory and generate a markdown report",
                data_dir=str(data_dir),
                thread_id="thread-demo",
                settings=settings,
            )

            workspace = Path(state.workspace_dir or "")
            self.assertEqual(state.status, "completed")
            self.assertTrue(bool(state.trace_id))
            self.assertEqual(state.task_type, "delegated_response")
            self.assertEqual(len(state.subagent_tasks), 1)
            self.assertEqual(len(state.subagent_results), 1)
            self.assertTrue((workspace / "workspace" / "data" / "notes.md").exists())
            self.assertTrue((workspace / "notes" / "research.md").exists())
            self.assertTrue((workspace / "outputs" / "final.md").exists())
            self.assertTrue((workspace / "subagents" / "manifest.json").exists())
            self.assertTrue((workspace / "subagents" / "task_001" / "result.md").exists())
            self.assertIn("subagents/manifest.json", state.artifact_files)
            self.assertIn("subagents/task_001/result.md", state.artifact_files)
            self.assertIn("notes/research.md", state.artifact_files)
            self.assertIn("outputs/final.md", state.artifact_files)
            self.assertTrue(bool(state.final_answer))


if __name__ == "__main__":
    unittest.main()
