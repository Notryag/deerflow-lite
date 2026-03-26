from __future__ import annotations

import shutil
from uuid import uuid4
from pathlib import Path

from app.agents.common import build_context
from app.agents.lead_agent import LeadAgent
from app.config.settings import Settings
from app.runtime.logger import close_run_logger, get_run_logger
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.reporting import write_final_report, write_research_notes
from app.tools.task_tool import TaskTool
from app.subagents.executor import SubagentExecutor
from app.subagents.rendering import build_fallback_subagent_prompt


def init_state(user_task: str, data_dir: str | None, thread_id: str | None = None) -> RunState:
    return RunState(
        thread_id=thread_id or uuid4().hex[:12],
        user_task=user_task,
        data_dir=data_dir,
        trace_id=uuid4().hex,
        status="pending",
    )


def run_task(
    user_task: str,
    data_dir: str | None = None,
    thread_id: str | None = None,
    settings: Settings | None = None,
) -> RunState:
    settings = settings or Settings.load()
    state = init_state(user_task=user_task, data_dir=data_dir, thread_id=thread_id)
    workspace = Workspace(settings.runtime_dir, state.thread_id).create()
    state.workspace_dir = str(workspace.thread_dir)
    state.add_artifact_file("subagents/manifest.json")

    logger = get_run_logger(workspace.logs_dir / "run.log")
    state.status = "running"
    logger.info("run started")
    workspace.write_text("input/task.md", user_task)
    if data_dir:
        _import_data_dir(workspace, data_dir)

    try:
        state = LeadAgent(settings).run(state, workspace)
        if state.task_type == "direct_response" and state.final_answer:
            state.status = "completed"
            logger.info("lead agent completed before legacy workflow")
            return state
        if state.task_type == "delegated_response" and state.final_answer:
            write_research_notes(state, workspace)
            write_final_report(state, workspace)
            state.status = "completed"
            logger.info("lead agent completed after delegation")
            return state

        delegated = _run_fallback_subagent(state, workspace, settings)
        if delegated:
            state.task_type = "delegated_response"

        write_research_notes(state, workspace)
        write_final_report(state, workspace)
        state.status = "completed"
        logger.info("run completed")
        return state
    except Exception as exc:
        state.status = "failed"
        state.errors.append(str(exc))
        logger.exception("run failed")
        raise
    finally:
        close_run_logger(logger)

def _run_fallback_subagent(state: RunState, workspace: Workspace, settings: Settings) -> bool:
    context = build_context(state, workspace)
    task = TaskTool(state, workspace).create_task(
        description="Investigate task context",
        prompt=build_fallback_subagent_prompt(state.user_task, context),
        subagent_type="general-purpose",
    )
    SubagentExecutor(settings).execute_task(state, workspace, task["task_id"])
    return True


def _import_data_dir(workspace: Workspace, data_dir: str) -> None:
    source_root = Path(data_dir).resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise ValueError(f"data_dir does not exist or is not a directory: {data_dir}")
    for source_path in source_root.rglob("*"):
        if not source_path.is_file():
            continue
        relative = source_path.relative_to(source_root).as_posix()
        target = workspace.resolve_path(f"workspace/data/{relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
