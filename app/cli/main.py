from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.workflows.run_task import run_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deerflow-lite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a DeerFlow Lite task.")
    run_parser.add_argument("task", help="User task to execute.")
    run_parser.add_argument("--data-dir", dest="data_dir", default=None, help="Path to local data directory.")
    run_parser.add_argument("--thread-id", dest="thread_id", default=None, help="Optional thread id.")
    run_parser.add_argument("--output", dest="output", default=None, help="Optional output file path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command != "run":
        parser.error("unknown command")

    state = run_task(user_task=args.task, data_dir=args.data_dir, thread_id=args.thread_id)
    payload = {
        "thread_id": state.thread_id,
        "status": state.status,
        "final_answer": state.final_answer,
        "workspace": state.workspace_dir,
        "final_output": str(Path(state.workspace_dir or ".") / "outputs" / "final.md"),
        "notes": state.notes_files,
        "outputs": state.output_files,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
