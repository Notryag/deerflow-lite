from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agents.common import build_chat_model, build_context, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.executor import SubagentExecutor
from app.subagents.rendering import build_lead_prompt
from app.tools.task_tool import TaskTool


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
        if use_stub_agents(self.settings):
            if not self._can_answer_in_stub(state):
                return state
            output = self._stub_output(state)
        else:
            output = self._langchain_output(state, workspace)

        return self._persist_output(state, workspace, output)

    @staticmethod
    def _can_answer_in_stub(state: RunState) -> bool:
        if state.data_dir:
            return False
        lower_task = state.user_task.lower().strip()
        return lower_task in {"hi", "hello", "hey"} or lower_task.startswith("say hello")

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

        task_tool = self._build_task_tool(state, workspace)

        @dynamic_prompt
        def inject_context(request):
            return build_lead_prompt(context)

        agent = create_agent(
            model=build_chat_model(self.settings),
            tools=[task_tool],
            middleware=[inject_context],
            response_format=LeadAgentOutput,
            name="deerflow_lite_lead",
        )
        result = agent.invoke({"messages": [{"role": "user", "content": state.user_task}]})
        structured = result.get("structured_response")
        if isinstance(structured, LeadAgentOutput):
            return structured
        return LeadAgentOutput.model_validate(structured)

    def _build_task_tool(self, state: RunState, workspace: Workspace):
        task_tool_impl = TaskTool(state, workspace)
        executor = SubagentExecutor(self.settings)

        @tool("task", parse_docstring=True)
        def delegate_task(
            description: str,
            prompt: str,
            subagent_type: Literal["general-purpose", "bash"],
            max_turns: int | None = None,
        ) -> str:
            """Delegate a task to a specialized subagent that runs in its own context.

            Subagents help you:
            - Preserve context by keeping exploration and implementation separate
            - Handle complex multi-step tasks autonomously
            - Execute commands or operations in isolated contexts

            Available subagent types:
            - general-purpose: Use for complex, multi-step tasks that require reasoning or synthesis.
            - bash: Use for command-heavy tasks or cases where command output would be verbose.

            When to use this tool:
            - Complex tasks requiring multiple steps or tools
            - Tasks that produce verbose output
            - When you want to isolate context from the main conversation

            When NOT to use this tool:
            - Simple, single-step operations
            - Tasks requiring user clarification

            Args:
                description: A short 3-5 word description of the delegated task.
                prompt: A specific self-contained prompt for the subagent.
                subagent_type: The subagent type to use.
                max_turns: Optional maximum number of turns for the subagent.
            """

            task = task_tool_impl.create_task(
                description=description,
                prompt=prompt,
                subagent_type=subagent_type,
                max_turns=max_turns,
            )
            result = executor.execute_task(state, workspace, task["task_id"])
            return json.dumps(result, ensure_ascii=True)

        return delegate_task
