from __future__ import annotations

from queue import Empty
from time import sleep
from typing import Any

from app.subagents.rendering import build_subagent_summary, render_subagent_result_markdown


def run_builtin_subagent(task: dict[str, Any], spec_name: str, spec_description: str) -> dict[str, str]:
    simulated_delay = float(task.get("simulated_delay_seconds", 0) or 0)
    if simulated_delay > 0:
        sleep(simulated_delay)

    artifact_path = f"subagents/{task['task_id']}/result.md"
    summary = build_subagent_summary(task, spec_name)
    artifact_body = render_subagent_result_markdown(task, spec_name, spec_description, summary)
    return {
        "artifact_path": artifact_path,
        "artifact_body": artifact_body,
        "summary": summary,
    }


def run_subagent_worker(
    task: dict[str, Any],
    spec_name: str,
    spec_description: str,
    result_queue: Any,
) -> None:
    try:
        result_queue.put(
            {
                "status": "completed",
                "body": run_builtin_subagent(task, spec_name, spec_description),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive child-process path
        result_queue.put({"status": "failed", "error": str(exc)})


def read_worker_message(result_queue: Any) -> dict[str, Any]:
    try:
        return result_queue.get(timeout=1)
    except Empty:
        return {"status": "failed", "error": "worker exited without producing a result"}
