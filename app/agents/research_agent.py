from __future__ import annotations

from app.agents.common import build_chat_model, build_context, format_context_block, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import ResearchNotes, build_research_notes_from_state, render_research_notes


class ResearchAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, state: RunState, workspace: Workspace) -> RunState:
        notes = self._stub_notes(state)
        if not use_stub_agents(self.settings):
            notes = self._langchain_notes(state, workspace)
            if (state.retrieved_docs or state.search_results) and not notes.evidence:
                notes = self._stub_notes(state)
        path = workspace.write_text("notes/research.md", render_research_notes(notes))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.notes_files:
            state.notes_files.append(relative)
        state.add_artifact_file(relative)
        return state

    def _stub_notes(self, state: RunState) -> ResearchNotes:
        return build_research_notes_from_state(state)

    def _langchain_notes(self, state: RunState, workspace: Workspace) -> ResearchNotes:
        from langchain.agents import create_agent
        from langchain.agents.middleware import dynamic_prompt

        context = build_context(state, workspace)
        base_prompt = (
            "Write structured research notes from the available materials. "
            "Keep findings concise and include open questions for missing information."
        )

        @dynamic_prompt
        def inject_context(request):
            return f"{base_prompt}\n\n{format_context_block(context)}"

        agent = create_agent(
            model=build_chat_model(self.settings),
            tools=[],
            middleware=[inject_context],
            response_format=ResearchNotes,
            name="deerflow_lite_research",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, ResearchNotes):
            return structured
        return ResearchNotes.model_validate(structured)
