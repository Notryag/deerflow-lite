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
            self.assertEqual(workspace.list_files(), ["notes/research.md"])

    def test_workspace_rejects_escaped_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-2").create()
            with self.assertRaises(ValueError):
                workspace.write_text("../evil.txt", "boom")


if __name__ == "__main__":
    unittest.main()
