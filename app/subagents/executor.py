from __future__ import annotations

from multiprocessing import get_context
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.builtins import read_worker_message, run_subagent_worker
from app.subagents.registry import SubagentRegistry
from app.tools.langchain_toolset import build_langchain_tools


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

        prepared = [self._prepare_task(state, workspace, task_id) for task_id in task_ids]
        results: list[dict[str, Any]] = []
        max_workers = max(1, min(len(prepared), self.settings.subagent_max_concurrency))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                (prepared_task, pool.submit(self._execute_isolated_task, prepared_task))
                for prepared_task in prepared
            ]

            for prepared_task, future in futures:
                task = prepared_task["task"]
                try:
                    execution = future.result()
                except Exception as exc:
                    result = self._mark_failed(state, workspace, task, str(exc))
                else:
                    if execution["status"] == "completed":
                        result = self._complete_task(
                            state,
                            workspace,
                            task,
                            execution["body"],
                            prepared_task["effective_timeout"],
                            float(execution["elapsed_seconds"]),
                        )
                    elif execution["status"] == "timeout":
                        result = self._mark_timeout(state, workspace, task, str(execution["error"]))
                    else:
                        result = self._mark_failed(state, workspace, task, str(execution["error"]))
                results.append(result)
        return results

    def execute_task(self, state: RunState, workspace: Workspace, task_id: str) -> dict[str, Any]:
        return self.execute_tasks(state, workspace, [task_id])[0]

    def _prepare_task(self, state: RunState, workspace: Workspace, task_id: str) -> dict[str, Any]:
        task = self._find_task(state, task_id)
        spec = self.registry.get(str(task["subagent_type"]))
        self._validate_task(task, spec.name)
        runtime_tools = [
            tool.name
            for tool in build_langchain_tools(
                state,
                workspace,
                self.settings,
                include_task=False,
                allowed_tool_names=spec.allowed_tools,
            )
        ]
        runtime_context = {
            "thread_id": state.thread_id,
            "runtime_dir": str(workspace.runtime_dir),
            "workspace_dir": str(workspace.thread_dir),
            "data_dir": state.data_dir,
            "vector_db_dir": str(self.settings.vector_db_dir),
            "user_task": state.user_task,
        }
        effective_timeout = min(
            float(task.get("timeout_seconds", spec.timeout_seconds)),
            float(self.settings.subagent_timeout_seconds),
        )
        if effective_timeout <= 0:
            raise ValueError("configured timeout must be greater than 0")
        enriched_task = {**task, "runtime_tools": runtime_tools, "runtime_context": runtime_context}
        return {"task": enriched_task, "spec": spec, "effective_timeout": effective_timeout}

    @staticmethod
    def _find_task(state: RunState, task_id: str) -> dict[str, Any]:
        for task in state.subagent_tasks:
            if str(task.get("task_id")) == task_id:
                return task
        raise ValueError(f"unknown task_id '{task_id}'")

    def _execute_isolated_task(self, prepared_task: dict[str, Any]) -> dict[str, Any]:
        task = prepared_task["task"]
        spec = prepared_task["spec"]
        effective_timeout = float(prepared_task["effective_timeout"])
        ctx = get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(
            target=run_subagent_worker,
            args=(task, spec.name, spec.description, result_queue),
        )

        started = perf_counter()
        process.start()
        process.join(timeout=effective_timeout)

        if process.is_alive():
            process.terminate()
            process.join()
            return {
                "status": "timeout",
                "error": f"subagent exceeded timeout after {effective_timeout:.3f}s",
            }

        elapsed_seconds = perf_counter() - started
        message = read_worker_message(result_queue)
        if message["status"] != "completed":
            return {"status": "failed", "error": message.get("error", "worker failed")}

        return {
            "status": "completed",
            "body": message["body"],
            "elapsed_seconds": round(elapsed_seconds, 6),
        }

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
