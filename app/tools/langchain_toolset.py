from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.file_ops import FileOpsToolset
from app.tools.python_exec import run_python_code
from app.tools.retrieval import retrieve_knowledge
from app.tools.task_tool import TaskTool
from app.tools.web_search import search_web


def build_langchain_tools(
    state: RunState,
    workspace: Workspace,
    settings: Settings,
    *,
    include_task: bool,
    allowed_tool_names: tuple[str, ...] | None = None,
) -> list[object]:
    file_ops = FileOpsToolset(workspace)
    task_tool_impl = TaskTool(state, workspace)

    @tool("retrieve_knowledge", parse_docstring=True)
    def retrieve_knowledge_tool(query: str, top_k: int = 3) -> str:
        """Retrieve relevant local context from the configured data directory.

        Args:
            query: The search query for local retrieval.
            top_k: Maximum number of retrieved chunks to return.
        """

        if not state.data_dir:
            raise ValueError("retrieve_knowledge requires a configured data_dir")
        results = retrieve_knowledge(
            query=query,
            data_dir=state.data_dir,
            settings=settings,
            top_k=top_k,
            collection_name=state.thread_id,
        )
        state.needs_retrieval = True
        state.retrieved_docs = results
        return json.dumps(results, ensure_ascii=True)

    @tool("search_web", parse_docstring=True)
    def search_web_tool(query: str, top_k: int = 5) -> str:
        """Search the web and return structured results.

        Args:
            query: The search query.
            top_k: Maximum number of results to return.
        """

        results = search_web(query, top_k=top_k)
        state.needs_web_search = True
        state.search_results = results
        return json.dumps(results, ensure_ascii=True)

    @tool("read_file", parse_docstring=True)
    def read_file_tool(path: str) -> str:
        """Read a file from the current workspace.

        Args:
            path: Relative path inside the current thread workspace.
        """

        return file_ops.read_file(path)

    @tool("write_file", parse_docstring=True)
    def write_file_tool(path: str, content: str) -> str:
        """Write a file inside the current workspace.

        Args:
            path: Relative path inside the current thread workspace.
            content: Text content to write.
        """

        written = file_ops.write_file(path, content)
        relative = str(workspace.relative_path(written)).replace("\\", "/")
        state.add_artifact_file(relative)
        return relative

    @tool("list_workspace_files", parse_docstring=True)
    def list_workspace_files_tool() -> str:
        """List files currently available in the thread workspace."""

        return json.dumps(file_ops.list_workspace_files(), ensure_ascii=True)

    @tool("run_python_code", parse_docstring=True)
    def run_python_code_tool(code: str, timeout_seconds: int = 10) -> str:
        """Run Python code inside the current workspace.

        Args:
            code: Python code to execute.
            timeout_seconds: Maximum execution time in seconds.
        """

        state.needs_python = True
        result = run_python_code(code, workspace, timeout_seconds=timeout_seconds)
        return json.dumps(result, ensure_ascii=True)

    tools: list[object] = [
        retrieve_knowledge_tool,
        search_web_tool,
        read_file_tool,
        write_file_tool,
        list_workspace_files_tool,
        run_python_code_tool,
    ]

    if include_task:
        from app.subagents.executor import SubagentExecutor

        executor = SubagentExecutor(settings)

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

        tools.append(delegate_task)

    if allowed_tool_names is None:
        return tools

    allowed = set(allowed_tool_names)
    return [item for item in tools if getattr(item, "name", "") in allowed]
