from __future__ import annotations

from queue import Empty
from time import sleep
from typing import Any


def build_summary(task: dict[str, Any], spec_name: str) -> str:
    description = str(task.get("description", "")).strip()
    prompt = str(task.get("prompt", "")).strip()
    prompt_excerpt = prompt[:160].strip()
    if len(prompt) > 160:
        prompt_excerpt += "..."
    return f"{spec_name} worker completed delegated task '{description}'. Prompt focus: {prompt_excerpt}"


def render_artifact(task: dict[str, Any], spec_name: str, spec_description: str, summary: str) -> str:
    return (
        "# Subagent Result\n\n"
        f"## Task ID\n{task['task_id']}\n\n"
        f"## Description\n{task['description']}\n\n"
        f"## Subagent Type\n{task['subagent_type']}\n\n"
        f"## Type Notes\n{spec_description}\n\n"
        f"## Worker\n{spec_name}\n\n"
        f"## Prompt\n{task['prompt']}\n\n"
        f"## Summary\n{summary}\n"
    )


def run_builtin_subagent(task: dict[str, Any], spec_name: str, spec_description: str) -> dict[str, str]:
    simulated_delay = float(task.get("simulated_delay_seconds", 0) or 0)
    if simulated_delay > 0:
        sleep(simulated_delay)

    artifact_path = f"subagents/{task['task_id']}/result.md"
    summary = build_summary(task, spec_name)
    artifact_body = render_artifact(task, spec_name, spec_description, summary)
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
