from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.common import build_context, format_context_block, normalize_bullets, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


class OrchestratorDecision(BaseModel):
    task_type: str
    plan: list[str] = Field(default_factory=list)
    needs_retrieval: bool = False
    needs_web_search: bool = False
    needs_python: bool = False


class OrchestratorAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, state: RunState, workspace: Workspace) -> RunState:
        decision = self._stub_decision(state.user_task)
        if not use_stub_agents(self.settings):
            decision = self._langchain_decision(state, workspace)
        state.task_type = decision.task_type
        state.plan = decision.plan
        state.needs_retrieval = decision.needs_retrieval
        state.needs_web_search = decision.needs_web_search
        state.needs_python = decision.needs_python
        return state

    def _stub_decision(self, task: str) -> OrchestratorDecision:
        lower_task = task.lower()
        needs_retrieval = any(token in lower_task for token in ("pdf", "doc", "docs", "document", "目录", "总结"))
        needs_web_search = any(token in lower_task for token in ("search", "web", "资料", "联网"))
        needs_python = any(token in lower_task for token in ("python", "code", "脚本"))
        plan = normalize_bullets(
            [
                "inspect the task and available local data",
                "retrieve relevant local context" if needs_retrieval else "",
                "search the web for missing context" if needs_web_search else "",
                "generate structured research notes",
                "write the final markdown output",
            ]
        )
        return OrchestratorDecision(
            task_type="research_report",
            plan=plan,
            needs_retrieval=needs_retrieval,
            needs_web_search=needs_web_search,
            needs_python=needs_python,
        )

    def _langchain_decision(self, state: RunState, workspace: Workspace) -> OrchestratorDecision:
        from langchain.agents import create_agent
        from langchain.agents.middleware import wrap_model_call
        from langchain.messages import SystemMessage

        context = build_context(state, workspace)

        @wrap_model_call
        def inject_context(request, handler):
            extra = {"type": "text", "text": format_context_block(context)}
            system_message = SystemMessage(content=list(request.system_message.content_blocks) + [extra])
            return handler(request.override(system_message=system_message))

        agent = create_agent(
            model=self.settings.model_name,
            tools=[],
            system_prompt=(
                "You are the orchestrator for DeerFlow Lite. "
                "Decide the task type and which capabilities are required."
            ),
            middleware=[inject_context],
            response_format=OrchestratorDecision,
            name="deerflow_lite_orchestrator",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, OrchestratorDecision):
            return structured
        return OrchestratorDecision.model_validate(structured)
