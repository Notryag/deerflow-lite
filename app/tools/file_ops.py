from __future__ import annotations

from app.runtime.workspace import Workspace


class FileOpsToolset:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def read_file(self, path: str) -> str:
        return self.workspace.read_text(path)

    def write_file(self, path: str, content: str) -> str:
        written = self.workspace.write_text(path, content)
        return str(written)

    def list_workspace_files(self) -> list[str]:
        return self.workspace.list_files()
