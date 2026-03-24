from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.workspace import Workspace
from app.tools.file_ops import FileOpsToolset


class FileOpsTests(unittest.TestCase):
    def test_file_ops_write_and_read_within_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-1").create()
            tools = FileOpsToolset(workspace)

            tools.write_file("notes/test.md", "hello")

            self.assertEqual(tools.read_file("notes/test.md"), "hello")
            self.assertIn("notes/test.md", tools.list_workspace_files())

    def test_file_ops_rejects_escaped_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-2").create()
            tools = FileOpsToolset(workspace)

            with self.assertRaises(ValueError):
                tools.write_file("../evil.txt", "boom")


if __name__ == "__main__":
    unittest.main()
