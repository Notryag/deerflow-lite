from __future__ import annotations

from uuid import uuid4

from app.agents.lead_agent import LeadAgent
from app.agents.orchestrator import OrchestratorAgent
from app.config.settings import Settings
from app.runtime.logger import close_run_logger, get_run_logger
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.retrieval import retrieve_knowledge
from app.tools.reporting import write_final_report, write_research_notes
from app.tools.web_search import search_web


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

    try:
        state = LeadAgent(settings).run(state, workspace)
        if state.task_type in {"direct_response", "delegated_response"} and state.final_answer:
            state.status = "completed"
            logger.info("lead agent completed before legacy workflow")
            return state

        state = OrchestratorAgent(settings).run(state, workspace)

        if state.needs_retrieval and data_dir:
            logger.info("running retrieval")
            state.retrieved_docs = retrieve_knowledge(
                query=user_task,
                data_dir=data_dir,
                settings=settings,
                top_k=3,
                collection_name=state.thread_id,
            )

        if state.needs_web_search:
            logger.info("running web search")
            state.search_results = search_web(user_task, top_k=3)

        if state.needs_python:
            logger.info("python execution requested but not enabled in workflow")

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
