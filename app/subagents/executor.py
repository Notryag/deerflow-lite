from __future__ import annotations

from time import perf_counter
from typing import Any

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.registry import SubagentRegistry


class SubagentExecutor:
    def __init__(self, settings: Settings, registry: SubagentRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or SubagentRegistry()

    def execute_tasks(self, state: RunState, workspace: Workspace, task_ids: list[str]) -> list[dict[str, Any]]:
        if len(task_ids) > self.settings.subagent_max_concurrency:
            raise ValueError(
                "requested task batch exceeds subagent_max_concurrency "
                f"({len(task_ids)} > {self.settings.subagent_max_concurrency})"
            )
        return [self.execute_task(state, workspace, task_id) for task_id in task_ids]

    def execute_task(self, state: RunState, workspace: Workspace, task_id: str) -> dict[str, Any]:
        task = self._find_task(state, task_id)
        spec = self.registry.get(str(task["subagent_type"]))
        self._validate_task(task, spec.name)
        effective_timeout = min(int(task.get("timeout_seconds", spec.timeout_seconds)), self.settings.subagent_timeout_seconds)
        if effective_timeout <= 0:
            return self._mark_timeout(state, workspace, task, "configured timeout is not positive")

        started = perf_counter()
        artifact_path = f"subagents/{task_id}/result.md"
        summary = self._build_summary(task)
        artifact_body = self._render_artifact(task, spec.description, summary)
        workspace.write_text(artifact_path, artifact_body)
        elapsed_seconds = perf_counter() - started

        if elapsed_seconds > effective_timeout:
            return self._mark_timeout(
                state,
                workspace,
                task,
                f"subagent exceeded timeout after {elapsed_seconds:.3f}s",
            )

        updated_task = {
            **task,
            "status": "completed",
            "effective_timeout_seconds": effective_timeout,
            "elapsed_seconds": round(elapsed_seconds, 6),
        }
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
            "elapsed_seconds": round(elapsed_seconds, 6),
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

    @staticmethod
    def _validate_task(task: dict[str, Any], resolved_type: str) -> None:
        if str(task.get("subagent_type")) != resolved_type:
            raise ValueError("task subagent_type does not match resolved registry type")
        allowed_tools = {str(item) for item in task.get("allowed_tools", [])}
        disallowed_tools = {str(item) for item in task.get("disallowed_tools", [])}
        if "task" in allowed_tools:
            raise ValueError("nested delegation is not allowed for subagent tasks")
        if "task" not in disallowed_tools:
            raise ValueError("subagent tasks must explicitly disallow the task tool")

    def _mark_timeout(
        self,
        state: RunState,
        workspace: Workspace,
        task: dict[str, Any],
        error: str,
    ) -> dict[str, Any]:
        updated_task = {**task, "status": "timeout"}
        state.record_subagent_task(**updated_task)
        workspace.append_manifest_task(updated_task)
        result = {
            "task_id": str(task["task_id"]),
            "status": "timeout",
            "summary": "",
            "artifacts": [],
            "citations": [],
            "error": error,
            "subagent_type": task["subagent_type"],
        }
        state.record_subagent_result(**result)
        workspace.append_manifest_result(result)
        return result
