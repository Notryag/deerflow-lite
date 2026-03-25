from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.registry import SubagentRegistry


class SubagentExecutor:
    def __init__(self, settings: Settings, registry: SubagentRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or SubagentRegistry()

    def execute_task(self, state: RunState, workspace: Workspace, task_id: str) -> dict[str, Any]:
        task = self._find_task(state, task_id)
        spec = self.registry.get(str(task["subagent_type"]))

        artifact_path = f"subagents/{task_id}/result.md"
        summary = self._build_summary(task)
        artifact_body = self._render_artifact(task, spec.description, summary)
        workspace.write_text(artifact_path, artifact_body)

        updated_task = {**task, "status": "completed"}
        state.record_subagent_task(**updated_task)
        workspace.append_manifest_task(updated_task)

        result = {
            "task_id": task_id,
            "status": "completed",
            "summary": summary,
            "artifacts": [artifact_path],
            "citations": [],
            "error": None,
            "subagent_type": task["subagent_type"],
        }
        state.record_subagent_result(**result)
        workspace.append_manifest_result(result)
        return result

    @staticmethod
    def _find_task(state: RunState, task_id: str) -> dict[str, Any]:
        for task in state.subagent_tasks:
            if str(task.get("task_id")) == task_id:
                return task
        raise ValueError(f"unknown task_id '{task_id}'")

    @staticmethod
    def _build_summary(task: dict[str, Any]) -> str:
        description = str(task.get("description", "")).strip()
        prompt = str(task.get("prompt", "")).strip()
        prompt_excerpt = prompt[:160].strip()
        if len(prompt) > 160:
            prompt_excerpt += "..."
        return f"Completed delegated task '{description}'. Prompt focus: {prompt_excerpt}"

    @staticmethod
    def _render_artifact(task: dict[str, Any], spec_description: str, summary: str) -> str:
        return (
            "# Subagent Result\n\n"
            f"## Task ID\n{task['task_id']}\n\n"
            f"## Description\n{task['description']}\n\n"
            f"## Subagent Type\n{task['subagent_type']}\n\n"
            f"## Type Notes\n{spec_description}\n\n"
            f"## Prompt\n{task['prompt']}\n\n"
            f"## Summary\n{summary}\n"
        )
