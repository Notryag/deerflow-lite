from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.common import build_chat_model, build_context, format_context_block, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


class LeadAgentOutput(BaseModel):
    final_answer: str
    sections: list[str] = Field(default_factory=list)


def render_lead_markdown(output: LeadAgentOutput) -> str:
    body = "\n\n".join(output.sections) if output.sections else output.final_answer
    return (
        "# Final Report\n\n"
        f"## Summary\n{output.final_answer}\n\n"
        f"## Report\n{body}\n"
    )


class LeadAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, state: RunState, workspace: Workspace) -> RunState:
        if not self._should_answer_directly(state):
            return state

        output = self._stub_output(state)
        if not use_stub_agents(self.settings):
            output = self._langchain_output(state, workspace)

        path = workspace.write_text("outputs/final.md", render_lead_markdown(output))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.output_files:
            state.output_files.append(relative)
        state.add_artifact_file(relative)
        state.final_answer = output.final_answer
        state.task_type = "direct_response"
        if not state.plan:
            state.plan = ["answer the task directly without delegation"]
        return state

    def _should_answer_directly(self, state: RunState) -> bool:
        if state.data_dir:
            return False

        lower_task = state.user_task.lower()
        complex_tokens = (
            "summarize",
            "summary",
            "report",
            "research",
            "analyze",
            "analysis",
            "compare",
            "docs",
            "document",
            "file",
            "search",
            "web",
            "latest",
            "recent",
            "retrieve",
            "rag",
            "python",
            "code",
            "script",
            "目录",
            "总结",
            "资料",
            "联网",
            "脚本",
        )
        return not any(token in lower_task for token in complex_tokens)

    def _stub_output(self, state: RunState) -> LeadAgentOutput:
        lower_task = state.user_task.lower().strip()
        if "hello" in lower_task or "hi" in lower_task:
            answer = "Hello."
        else:
            answer = "Completed the task directly without delegation."
        sections = [
            f"### Task\n{state.user_task}",
            "### Execution\nThe lead agent answered this request directly because it did not require retrieval or subagent delegation.",
        ]
        return LeadAgentOutput(final_answer=answer, sections=sections)

    def _langchain_output(self, state: RunState, workspace: Workspace) -> LeadAgentOutput:
        from langchain.agents import create_agent
        from langchain.agents.middleware import dynamic_prompt

        context = build_context(state, workspace)
        base_prompt = (
            "You are the DeerFlow Lite lead agent. "
            "Answer the user's request directly without delegating. "
            "Keep the answer concise and self-contained."
        )

        @dynamic_prompt
        def inject_context(request):
            return f"{base_prompt}\n\n{format_context_block(context)}"

        agent = create_agent(
            model=build_chat_model(self.settings),
            tools=[],
            middleware=[inject_context],
            response_format=LeadAgentOutput,
            name="deerflow_lite_lead",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, LeadAgentOutput):
            return structured
        return LeadAgentOutput.model_validate(structured)
