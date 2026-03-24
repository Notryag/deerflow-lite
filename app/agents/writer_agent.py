from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.common import build_context, extract_evidence, format_context_block, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


class WriterOutput(BaseModel):
    final_answer: str
    sections: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


def render_final_markdown(output: WriterOutput) -> str:
    body = "\n\n".join(output.sections) if output.sections else "No report body was generated."
    evidence = "\n".join(f"- {item}" for item in output.evidence) or "- No cited evidence."
    return (
        "# Final Report\n\n"
        f"## Summary\n{output.final_answer}\n\n"
        f"## Report\n{body}\n\n"
        f"## Evidence\n{evidence}\n"
    )


class WriterAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, state: RunState, workspace: Workspace) -> RunState:
        output = self._stub_output(state, workspace)
        if not use_stub_agents(self.settings):
            output = self._langchain_output(state, workspace)
        path = workspace.write_text("outputs/final.md", render_final_markdown(output))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.output_files:
            state.output_files.append(relative)
        state.final_answer = output.final_answer
        return state

    def _stub_output(self, state: RunState, workspace: Workspace) -> WriterOutput:
        notes_excerpt = ""
        if state.notes_files:
            notes_excerpt = workspace.read_text(state.notes_files[0])[:500].strip()
        sections = [
            "### Workflow\nThis run used an explicit orchestrator, file-backed workspace, and structured state transitions.",
            f"### Task\n{state.user_task}",
        ]
        if notes_excerpt:
            sections.append(f"### Notes digest\n{notes_excerpt}")
        evidence = extract_evidence(state.retrieved_docs) + extract_evidence(state.search_results)
        summary = "Generated a markdown report from the available task context and collected notes."
        if state.retrieved_docs:
            summary = "Generated a markdown report using retrieved local context and structured research notes."
        return WriterOutput(final_answer=summary, sections=sections, evidence=evidence)

    def _langchain_output(self, state: RunState, workspace: Workspace) -> WriterOutput:
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
                "Write a concise final markdown report. "
                "Distinguish facts grounded in retrieved material from synthesis."
            ),
            middleware=[inject_context],
            response_format=WriterOutput,
            name="deerflow_lite_writer",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, WriterOutput):
            return structured
        return WriterOutput.model_validate(structured)
