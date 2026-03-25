from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agents.common import build_chat_model, build_context, format_context_block, use_stub_agents
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.executor import SubagentExecutor
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
        if state.data_dir:
            return state

        if use_stub_agents(self.settings):
            if self._should_delegate(state):
                return self._delegate_task(state, workspace)
            if not self._should_answer_directly(state):
                return state
            output = self._stub_output(state)
        else:
            output = self._langchain_output(state, workspace)

        return self._persist_output(state, workspace, output)

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

    def _should_delegate(self, state: RunState) -> bool:
        if state.data_dir:
            return False
        lower_task = state.user_task.lower()
        delegation_tokens = (
            "delegate",
            "subagent",
            "break down",
            "investigate",
            "inspect",
            "analyze",
            "analysis",
            "plan",
        )
        blocked_tokens = (
            "latest",
            "recent",
            "search",
            "web",
            "python",
            "code",
            "script",
            "联网",
            "资料",
            "脚本",
        )
        return any(token in lower_task for token in delegation_tokens) and not any(
            token in lower_task for token in blocked_tokens
        )

    def _delegate_task(self, state: RunState, workspace: Workspace) -> RunState:
        task_tool = TaskTool(state, workspace)
        task_result = task_tool.create_task(
            description=f"Handle delegated request: {state.user_task}",
            prompt=(
                "Work only inside the shared workspace. "
                "Return a concise summary and write a result artifact for the parent agent. "
                f"User task: {state.user_task}"
            ),
        )
        result = SubagentExecutor(self.settings).execute_task(state, workspace, task_result["task_id"])

        output = LeadAgentOutput(
            final_answer="Completed the task via a delegated subagent.",
            sections=[
                f"### Task\n{state.user_task}",
                f"### Delegation\nCreated subagent task `{task_result['task_id']}` of type `{task_result['subagent_type']}`.",
                f"### Result\n{result['summary']}",
            ],
        )
        path = workspace.write_text("outputs/final.md", render_lead_markdown(output))
        relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
        if relative not in state.output_files:
            state.output_files.append(relative)
        state.add_artifact_file(relative)
        state.final_answer = output.final_answer
        state.task_type = "delegated_response"
        if not state.plan:
            state.plan = [
                "create a delegated subagent task",
                "collect the structured subagent result",
                "write the final report from delegated output",
            ]
        return state

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
        base_prompt = (
            "You are the DeerFlow Lite lead agent. "
            "Decide whether to answer directly or delegate by calling the task tool. "
            "Use the task tool for complex, multi-step work that benefits from isolated context. "
            "Do not delegate simple single-step requests. "
            "After any tool use, produce a concise final answer."
        )

        task_tool = self._build_task_tool(state, workspace)

        @dynamic_prompt
        def inject_context(request):
            return f"{base_prompt}\n\n{format_context_block(context)}"

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
