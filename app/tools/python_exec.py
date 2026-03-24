from __future__ import annotations

import subprocess

from app.runtime.workspace import Workspace


def run_python_code(code: str, workspace: Workspace, timeout_seconds: int = 10) -> dict[str, object]:
    process = subprocess.run(
        ["python", "-c", code],
        cwd=str(workspace.thread_dir),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "artifacts": workspace.list_files(),
    }
