from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def test_workspace_create_and_list_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-1").create()
            workspace.write_text("notes/research.md", "hello")
            self.assertEqual(
                workspace.list_files(),
                ["notes/research.md", "subagents/manifest.json"],
            )
            self.assertTrue(workspace.workspace_data_dir.exists())

    def test_workspace_rejects_escaped_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-2").create()
            with self.assertRaises(ValueError):
                workspace.write_text("../evil.txt", "boom")

    def test_workspace_manifest_append_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-3").create()
            workspace.append_manifest_task(
                {
                    "task_id": "task-1",
                    "description": "Inspect docs",
                    "subagent_type": "general-purpose",
                    "status": "pending",
                }
            )
            workspace.append_manifest_result(
                {
                    "task_id": "task-1",
                    "status": "completed",
                    "summary": "done",
                    "artifacts": ["workspace/notes/inspect.md"],
                }
            )
            manifest = workspace.load_manifest()
            self.assertEqual(manifest["thread_id"], "thread-3")
            self.assertEqual(manifest["tasks"][0]["task_id"], "task-1")
            self.assertEqual(manifest["results"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
