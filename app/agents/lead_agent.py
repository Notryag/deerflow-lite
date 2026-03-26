from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.agents.common import build_chat_model, build_context
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import build_lead_prompt
from app.tools.langchain_toolset import build_langchain_tools


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
        output = self._langchain_output(state, workspace)
        return self._persist_output(state, workspace, output)

    def _persist_output(self, state: RunState, workspace: Workspace, output: LeadAgentOutput) -> RunState:
        path = workspace.write_text("outputs/final.md", render_lead_markdown(output))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.output_files:
            state.output_files.append(relative)
        state.add_artifact_file(relative)
        state.final_answer = output.final_answer
        if state.subagent_results:
            state.task_type = "delegated_response"
            if not state.plan:
                state.plan = [
                    "delegate a task to a subagent",
                    "collect the structured subagent result",
                    "write the final report from delegated output",
                ]
        else:
            state.task_type = "direct_response"
            if not state.plan:
                state.plan = ["answer the task directly without delegation"]
        return state

    def _langchain_output(self, state: RunState, workspace: Workspace) -> LeadAgentOutput:
        from langchain.agents import create_agent
        from langchain.agents.middleware import dynamic_prompt

        context = build_context(state, workspace)

        @dynamic_prompt
        def inject_context(request):
            return build_lead_prompt(context)

        agent = create_agent(
            model=build_chat_model(self.settings),
            tools=build_langchain_tools(state, workspace, self.settings, include_task=True),
            middleware=[inject_context],
            response_format=LeadAgentOutput,
            name="deerflow_lite_lead",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, LeadAgentOutput):
            return structured
        if isinstance(structured, dict):
            return LeadAgentOutput.model_validate(structured)
        content = self._extract_final_content(result)
        parsed = self._parse_output_content(content)
        if parsed:
            return LeadAgentOutput.model_validate(parsed)
        return LeadAgentOutput(
            final_answer=content or "Completed the task.",
            sections=[f"### Task\n{state.user_task}"],
        )

    @staticmethod
    def _extract_final_content(result: dict[str, object]) -> str:
        messages = result.get("messages", [])
        if isinstance(messages, list):
            for message in reversed(messages):
                content = getattr(message, "content", None)
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""

    @staticmethod
    def _parse_output_content(content: str) -> dict[str, object] | None:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed
