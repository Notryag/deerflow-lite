from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.common import (
    build_chat_model,
    build_context,
    extract_evidence,
    format_context_block,
    normalize_bullets,
    use_stub_agents,
)
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


class ResearchNotes(BaseModel):
    user_task: str
    key_findings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


def render_research_notes(notes: ResearchNotes) -> str:
    finding_lines = "\n".join(f"- {item}" for item in notes.key_findings) or "- No findings."
    evidence_lines = "\n".join(f"{idx}. {item}" for idx, item in enumerate(notes.evidence, start=1)) or "1. No evidence."
    question_lines = "\n".join(f"- {item}" for item in notes.open_questions) or "- None."
    return (
        "# Research Notes\n\n"
        f"## User task\n{notes.user_task}\n\n"
        f"## Key findings\n{finding_lines}\n\n"
        f"## Evidence\n{evidence_lines}\n\n"
        f"## Open questions\n{question_lines}\n"
    )


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
        return state

    def _stub_notes(self, state: RunState) -> ResearchNotes:
        findings = normalize_bullets(
            [
                f"Task type: {state.task_type or 'research_report'}",
                "Local retrieval was used." if state.retrieved_docs else "",
                "Web search was used." if state.search_results else "",
                "The workflow is running with explicit orchestration and file outputs.",
            ]
        )
        evidence = extract_evidence(state.retrieved_docs) + extract_evidence(state.search_results)
        open_questions = [] if evidence else ["No external evidence was available; output is based on task and workflow defaults."]
        return ResearchNotes(
            user_task=state.user_task,
            key_findings=findings,
            evidence=evidence,
            open_questions=open_questions,
        )

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
