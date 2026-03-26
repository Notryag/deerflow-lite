from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import sleep
from typing import Any

from app.config.settings import Settings
from app.runtime.workspace import Workspace
from app.tools.python_exec import run_python_code
from app.tools.retrieval import retrieve_knowledge
from app.tools.web_search import search_web
from app.subagents.rendering import build_subagent_summary, render_subagent_result_markdown


def run_builtin_subagent(task: dict[str, Any], spec_name: str, spec_description: str) -> dict[str, str]:
    simulated_delay = float(task.get("simulated_delay_seconds", 0) or 0)
    if simulated_delay > 0:
        sleep(simulated_delay)

    executed_tools, observations = execute_runtime_tools(task)
    task_with_results = {**task, "executed_tools": executed_tools, "tool_observations": observations}
    artifact_path = f"subagents/{task['task_id']}/result.md"
    summary = build_subagent_summary(task_with_results, spec_name)
    artifact_body = render_subagent_result_markdown(task_with_results, spec_name, spec_description, summary)
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


def execute_runtime_tools(task: dict[str, Any]) -> tuple[list[str], list[str]]:
    runtime_tools = {str(item) for item in task.get("runtime_tools", []) if str(item).strip()}
    runtime_context = dict(task.get("runtime_context", {}) or {})
    workspace = _workspace_from_task(runtime_context)
    executed: list[str] = []
    observations: list[str] = []

    if "list_workspace_files" in runtime_tools and workspace is not None:
        files = workspace.list_files()
        executed.append("list_workspace_files")
        observations.append(f"list_workspace_files returned {len(files)} files")

    if "read_file" in runtime_tools and workspace is not None:
        for relative_path in task.get("read_paths", []) or []:
            content = workspace.read_text(str(relative_path))
            executed.append("read_file")
            observations.append(f"read_file read {relative_path}: {content[:120].strip()}")

    if "write_file" in runtime_tools and workspace is not None:
        for item in task.get("writes", []) or []:
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", ""))
            if not path:
                continue
            workspace.write_text(path, content)
            executed.append("write_file")
            observations.append(f"write_file wrote {path}")

    if "retrieve_knowledge" in runtime_tools and runtime_context.get("data_dir"):
        settings = Settings(vector_db_dir=Path(str(runtime_context["vector_db_dir"])))
        query = resolve_tool_query(task, runtime_context)
        results = retrieve_knowledge(
            query=query,
            data_dir=str(runtime_context["data_dir"]),
            settings=settings,
            top_k=3,
            collection_name=str(runtime_context.get("thread_id", "default")),
        )
        executed.append("retrieve_knowledge")
        observations.append(f"retrieve_knowledge returned {len(results)} results for query '{query}'")

    if "search_web" in runtime_tools:
        query = resolve_tool_query(task, runtime_context)
        results = search_web(query, top_k=3)
        executed.append("search_web")
        observations.append(f"search_web returned {len(results)} results for query '{query}'")

    if "run_python_code" in runtime_tools and workspace is not None and task.get("python_code"):
        result = run_python_code(
            str(task.get("python_code", "")),
            workspace,
            timeout_seconds=int(task.get("python_timeout_seconds", 10) or 10),
        )
        executed.append("run_python_code")
        observations.append(
            f"run_python_code exited {result['returncode']} with stdout: {str(result['stdout']).strip()[:120]}"
        )

    return executed, observations


def _workspace_from_task(runtime_context: dict[str, Any]) -> Workspace | None:
    runtime_dir = runtime_context.get("runtime_dir")
    thread_id = runtime_context.get("thread_id")
    if not runtime_dir or not thread_id:
        return None
    return Workspace(Path(str(runtime_dir)), str(thread_id))


def resolve_tool_query(task: dict[str, Any], runtime_context: dict[str, Any]) -> str:
    for candidate in (
        task.get("query"),
        runtime_context.get("user_task"),
        task.get("description"),
        task.get("prompt"),
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return "subagent task"
