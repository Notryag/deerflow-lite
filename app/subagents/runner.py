from __future__ import annotations

import json
from pathlib import Path
from queue import Empty
from time import sleep
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.common import build_chat_model
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import build_subagent_summary, render_subagent_result_markdown
from app.tools.langchain_toolset import build_langchain_tools


def run_subagent(task: dict[str, Any], spec_name: str, spec_description: str, settings: Settings) -> dict[str, Any]:
    simulated_delay = float(task.get("simulated_delay_seconds", 0) or 0)
    if simulated_delay > 0:
        sleep(simulated_delay)

    state, workspace = _build_runtime_state(task)
    tools = build_langchain_tools(
        state,
        workspace,
        settings,
        include_task=False,
        allowed_tool_names=tuple(str(item) for item in task.get("runtime_tools", [])),
    )
    agent = create_agent(
        model=build_chat_model(settings),
        tools=tools,
        name=f"deerflow_lite_subagent_{spec_name}",
    )
    result = agent.invoke({"messages": [{"role": "user", "content": str(task.get("prompt", "")).strip()}]})
    final_content = _extract_final_content(result)
    executed_tools, observations = _extract_tool_trace(result)

    task_with_results = {
        **task,
        "executed_tools": executed_tools,
        "tool_observations": observations,
    }
    summary = final_content or build_subagent_summary(task_with_results, spec_name)
    artifact_path = f"subagents/{task['task_id']}/result.md"
    artifact_body = render_subagent_result_markdown(task_with_results, spec_name, spec_description, summary)
    citations = _extract_citations(state)
    extra_artifacts = [path for path in state.artifact_files if path != artifact_path]
    return {
        "artifact_path": artifact_path,
        "artifact_body": artifact_body,
        "summary": summary,
        "artifacts": [artifact_path, *extra_artifacts],
        "citations": citations,
    }


def run_subagent_worker(
    task: dict[str, Any],
    spec_name: str,
    spec_description: str,
    settings: Settings,
    result_queue: Any,
) -> None:
    try:
        result_queue.put(
            {
                "status": "completed",
                "body": run_subagent(task, spec_name, spec_description, settings),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive child-process path
        result_queue.put({"status": "failed", "error": str(exc)})


def read_worker_message(result_queue: Any) -> dict[str, Any]:
    try:
        return result_queue.get(timeout=1)
    except Empty:
        return {"status": "failed", "error": "worker exited without producing a result"}


def _build_runtime_state(task: dict[str, Any]) -> tuple[RunState, Workspace]:
    runtime_context = dict(task.get("runtime_context", {}) or {})
    runtime_dir = Path(str(runtime_context.get("runtime_dir", ".")))
    thread_id = str(runtime_context.get("thread_id", "subagent"))
    workspace = Workspace(runtime_dir, thread_id).create()
    state = RunState(
        thread_id=thread_id,
        user_task=str(task.get("prompt", "")).strip() or str(runtime_context.get("user_task", "")),
        data_dir=_optional_str(runtime_context.get("data_dir")),
        workspace_dir=str(workspace.thread_dir),
        trace_id=_optional_str(runtime_context.get("trace_id")),
        status="running",
    )
    return state, workspace


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _extract_final_content(result: dict[str, Any]) -> str:
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage):
            content = str(message.content).strip()
            if content:
                return content
    return ""


def _extract_tool_trace(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    executed: list[str] = []
    observations: list[str] = []
    for message in result.get("messages", []):
        if isinstance(message, AIMessage):
            for tool_call in getattr(message, "tool_calls", []) or []:
                name = str(tool_call.get("name", "")).strip()
                if name:
                    executed.append(name)
        if isinstance(message, ToolMessage):
            name = message.name or "tool"
            observations.append(f"{name} -> {_summarize_content(message.content)}")
    return executed, observations


def _summarize_content(content: Any) -> str:
    if isinstance(content, list):
        text = json.dumps(content, ensure_ascii=True)
    else:
        text = str(content).strip().replace("\n", " ")
    snippet = text[:180].strip()
    if len(text) > 180:
        snippet += "..."
    return snippet or "no output"


def _extract_citations(state: RunState) -> list[str]:
    citations: list[str] = []
    for item in state.retrieved_docs:
        source = str(item.get("source", "")).strip()
        if source and source not in citations:
            citations.append(source)
    for item in state.search_results:
        source = str(item.get("source", "")).strip()
        if source and source not in citations:
            citations.append(source)
    return citations
