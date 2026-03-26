from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool

from app.subagents.rendering import build_delegated_final_answer, build_delegated_final_sections


class LocalToolCallingChatModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "deerflow-lite-local-tool-calling"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        return RunnableLambda(lambda messages_input, config=None: self._bound_invoke(messages_input, tools))

    def _bound_invoke(
        self,
        messages_input: Any,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
    ) -> AIMessage:
        messages = self._coerce_messages(messages_input)
        tool_names = {self._tool_name(item) for item in tools}
        if "task" in tool_names:
            return self._lead_response(messages)
        return self._subagent_response(messages, tool_names)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self._fallback_content(messages)))])

    def _lead_response(self, messages: list[BaseMessage]) -> AIMessage:
        user_text = self._last_user_text(messages)
        task_result = self._last_tool_message(messages, "task")
        if task_result is not None:
            payload = self._build_delegated_payload(user_text, task_result)
            return AIMessage(content=json.dumps(payload, ensure_ascii=True))

        if self._is_simple_greeting(user_text):
            payload = {
                "final_answer": "Hello.",
                "sections": [
                    f"### Task\n{user_text}",
                    "### Execution\nThe lead agent answered directly without delegating.",
                ],
            }
            return AIMessage(content=json.dumps(payload, ensure_ascii=True))

        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {
                        "description": "Investigate task context",
                        "prompt": user_text or "Inspect the delegated task and summarize the result.",
                        "subagent_type": "general-purpose",
                    },
                    "id": "call_task_1",
                    "type": "tool_call",
                }
            ],
        )

    def _subagent_response(self, messages: list[BaseMessage], tool_names: set[str]) -> AIMessage:
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        if not tool_messages:
            first_tool_call = self._first_subagent_tool_call(messages, tool_names)
            if first_tool_call is not None:
                return first_tool_call
            return AIMessage(content=self._fallback_content(messages))

        latest_tool = tool_messages[-1]
        if latest_tool.name == "list_workspace_files" and "read_file" in tool_names:
            file_path = self._first_file_path(latest_tool.content)
            if file_path:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"path": file_path},
                            "id": "call_read_file_1",
                            "type": "tool_call",
                        }
                    ],
                )

        observation = self._summarize_tool_message(latest_tool)
        return AIMessage(content=f"Completed the delegated task. {observation}")

    @staticmethod
    def _coerce_messages(messages_input: Any) -> list[BaseMessage]:
        if isinstance(messages_input, list):
            return list(messages_input)
        if isinstance(messages_input, dict):
            payload = messages_input.get("messages", [])
            if isinstance(payload, list):
                return list(payload)
        return []

    @staticmethod
    def _tool_name(tool: dict[str, Any] | type | Any | BaseTool) -> str:
        return str(getattr(tool, "name", "")).strip()

    @staticmethod
    def _last_user_text(messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return str(message.content).strip()
        return ""

    @staticmethod
    def _last_tool_message(messages: list[BaseMessage], name: str) -> ToolMessage | None:
        for message in reversed(messages):
            if isinstance(message, ToolMessage) and message.name == name:
                return message
        return None

    @staticmethod
    def _is_simple_greeting(text: str) -> bool:
        lowered = text.lower().strip()
        return lowered in {"hi", "hello", "hey"} or lowered.startswith("say hello")

    def _build_delegated_payload(self, user_text: str, task_result: ToolMessage) -> dict[str, Any]:
        result = self._parse_json(task_result.content)
        task_id = str(result.get("task_id", "task_001"))
        subagent_type = str(result.get("subagent_type", "general-purpose"))
        result_summary = str(result.get("summary", "")).strip() or "The delegated task completed."
        return {
            "final_answer": build_delegated_final_answer(),
            "sections": build_delegated_final_sections(
                user_task=user_text or "Complete the delegated task.",
                task_id=task_id,
                subagent_type=subagent_type,
                result_summary=result_summary,
            ),
        }

    def _first_subagent_tool_call(self, messages: list[BaseMessage], tool_names: set[str]) -> AIMessage | None:
        prompt = self._last_user_text(messages)
        query = self._short_query(prompt)
        if "list_workspace_files" in tool_names:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_workspace_files",
                        "args": {},
                        "id": "call_list_workspace_files_1",
                        "type": "tool_call",
                    }
                ],
            )
        if "search_web" in tool_names and self._looks_like_web_search(prompt):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_web",
                        "args": {"query": query, "top_k": 3},
                        "id": "call_search_web_1",
                        "type": "tool_call",
                    }
                ],
            )
        return None

    @staticmethod
    def _first_file_path(content: str | list[str]) -> str | None:
        if isinstance(content, list):
            files = [str(item).strip() for item in content if str(item).strip()]
        else:
            try:
                parsed = json.loads(str(content))
            except json.JSONDecodeError:
                parsed = []
            if not isinstance(parsed, list):
                return None
            files = [str(item).strip() for item in parsed if str(item).strip()]
        for file_path in files:
            if file_path.startswith(("workspace/data/", "workspace/")):
                return file_path
        for file_path in files:
            if file_path.startswith(("logs/", "outputs/", "notes/", "subagents/", "input/")):
                continue
            return file_path
        return None

    @staticmethod
    def _summarize_tool_message(message: ToolMessage) -> str:
        name = message.name or "tool"
        content = str(message.content).strip().replace("\n", " ")
        snippet = content[:160].strip()
        if len(content) > 160:
            snippet += "..."
        if not snippet:
            snippet = "no output"
        return f"Used `{name}` and observed: {snippet}"

    @staticmethod
    def _fallback_content(messages: list[BaseMessage]) -> str:
        prompt = LocalToolCallingChatModel._last_user_text(messages)
        if LocalToolCallingChatModel._is_simple_greeting(prompt):
            return json.dumps(
                {
                    "final_answer": "Hello.",
                    "sections": [
                        f"### Task\n{prompt}",
                        "### Execution\nThe lead agent answered directly without delegating.",
                    ],
                },
                ensure_ascii=True,
            )
        return f"Completed the task. Prompt: {prompt[:160].strip()}"

    @staticmethod
    def _parse_json(value: Any) -> dict[str, Any]:
        try:
            parsed = json.loads(str(value))
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @staticmethod
    def _short_query(text: str) -> str:
        cleaned = " ".join(text.split())
        if not cleaned:
            return "delegated task"
        return cleaned[:120]

    @staticmethod
    def _looks_like_web_search(prompt: str) -> bool:
        lowered = prompt.lower()
        return any(term in lowered for term in ("web", "search", "latest", "recent", "news"))
