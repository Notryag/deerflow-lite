from __future__ import annotations

from app.agents.common import build_chat_model, build_context, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import (
    WriterOutput,
    build_writer_output_from_state,
    build_writer_prompt,
    render_final_markdown,
)


class WriterAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, state: RunState, workspace: Workspace) -> RunState:
        output = self._stub_output(state, workspace)
        if not use_stub_agents(self.settings):
            output = self._langchain_output(state, workspace)
            if not output.sections or ((state.retrieved_docs or state.search_results) and not output.evidence):
                output = self._stub_output(state, workspace)
        path = workspace.write_text("outputs/final.md", render_final_markdown(output))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.output_files:
            state.output_files.append(relative)
        state.add_artifact_file(relative)
        state.final_answer = output.final_answer
        return state

    def _stub_output(self, state: RunState, workspace: Workspace) -> WriterOutput:
        return build_writer_output_from_state(state, workspace)

    def _langchain_output(self, state: RunState, workspace: Workspace) -> WriterOutput:
        from langchain.agents import create_agent
        from langchain.agents.middleware import dynamic_prompt

        context = build_context(state, workspace)

        @dynamic_prompt
        def inject_context(request):
            return build_writer_prompt(context)

        agent = create_agent(
            model=build_chat_model(self.settings),
            tools=[],
            middleware=[inject_context],
            response_format=WriterOutput,
            name="deerflow_lite_writer",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, WriterOutput):
            return structured
        return WriterOutput.model_validate(structured)
