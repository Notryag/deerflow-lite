from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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

        prepared = [self._prepare_task(state, task_id) for task_id in task_ids]
        results: list[dict[str, Any]] = []
        max_workers = max(1, min(len(prepared), self.settings.subagent_max_concurrency))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                (
                    prepared_task,
                    pool.submit(self._run_task_body, prepared_task["task"], prepared_task["spec"].description),
                )
                for prepared_task in prepared
            ]

            for prepared_task, future in futures:
                task = prepared_task["task"]
                effective_timeout = prepared_task["effective_timeout"]
                started = perf_counter()
                try:
                    body = future.result(timeout=effective_timeout)
                except FutureTimeoutError:
                    future.cancel()
                    result = self._mark_timeout(
                        state,
                        workspace,
                        task,
                        f"subagent exceeded timeout after {effective_timeout:.3f}s",
                    )
                except Exception as exc:
                    result = self._mark_failed(state, workspace, task, str(exc))
                else:
                    elapsed_seconds = perf_counter() - started
                    result = self._complete_task(state, workspace, task, body, effective_timeout, elapsed_seconds)
                results.append(result)
        return results

    def execute_task(self, state: RunState, workspace: Workspace, task_id: str) -> dict[str, Any]:
        return self.execute_tasks(state, workspace, [task_id])[0]

    def _prepare_task(self, state: RunState, task_id: str) -> dict[str, Any]:
        task = self._find_task(state, task_id)
        spec = self.registry.get(str(task["subagent_type"]))
        self._validate_task(task, spec.name)
        effective_timeout = min(
            float(task.get("timeout_seconds", spec.timeout_seconds)),
            float(self.settings.subagent_timeout_seconds),
        )
        if effective_timeout <= 0:
            raise ValueError("configured timeout must be greater than 0")
        return {"task": task, "spec": spec, "effective_timeout": effective_timeout}

    @staticmethod
    def _find_task(state: RunState, task_id: str) -> dict[str, Any]:
        for task in state.subagent_tasks:
            if str(task.get("task_id")) == task_id:
                return task
        raise ValueError(f"unknown task_id '{task_id}'")

    def _run_task_body(self, task: dict[str, Any], spec_description: str) -> dict[str, str]:
        artifact_path = f"subagents/{task['task_id']}/result.md"
        summary = self._build_summary(task)
        artifact_body = self._render_artifact(task, spec_description, summary)
        return {
            "artifact_path": artifact_path,
            "artifact_body": artifact_body,
            "summary": summary,
        }

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

    def _complete_task(
        self,
        state: RunState,
        workspace: Workspace,
        task: dict[str, Any],
        body: dict[str, str],
        effective_timeout: float,
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        workspace.write_text(body["artifact_path"], body["artifact_body"])
        updated_task = {
            **task,
            "status": "completed",
            "effective_timeout_seconds": effective_timeout,
            "elapsed_seconds": round(elapsed_seconds, 6),
        }
        state.record_subagent_task(**updated_task)
        workspace.append_manifest_task(updated_task)

        result = {
            "task_id": str(task["task_id"]),
            "status": "completed",
            "summary": body["summary"],
            "artifacts": [body["artifact_path"]],
            "citations": [],
            "error": None,
            "subagent_type": task["subagent_type"],
            "elapsed_seconds": round(elapsed_seconds, 6),
        }
        state.record_subagent_result(**result)
        workspace.append_manifest_result(result)
        return result

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

    def _mark_failed(
        self,
        state: RunState,
        workspace: Workspace,
        task: dict[str, Any],
        error: str,
    ) -> dict[str, Any]:
        updated_task = {**task, "status": "failed"}
        state.record_subagent_task(**updated_task)
        workspace.append_manifest_task(updated_task)
        result = {
            "task_id": str(task["task_id"]),
            "status": "failed",
            "summary": "",
            "artifacts": [],
            "citations": [],
            "error": error,
            "subagent_type": task["subagent_type"],
        }
        state.record_subagent_result(**result)
        workspace.append_manifest_result(result)
        return result
