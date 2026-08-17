from __future__ import annotations

from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.config import get_config
from langgraph.runtime import Runtime

from ...title import ConversationTitleService


class TitleMiddlewareState(AgentState):
    title: NotRequired[str | None]


class TitleMiddleware(AgentMiddleware[TitleMiddlewareState]):
    """Generate one thread title after the first model exchange."""

    state_schema = TitleMiddlewareState

    def __init__(self, *, service: ConversationTitleService) -> None:
        super().__init__()
        self._service = service

    @staticmethod
    def _message_type(message: object) -> str | None:
        message_type = getattr(message, "type", None)
        if message_type is None and isinstance(message, dict):
            message_type = message.get("type") or message.get("role")
        if message_type == "user":
            return "human"
        if message_type == "assistant":
            return "ai"
        return message_type if isinstance(message_type, str) else None

    @staticmethod
    def _message_content(message: object) -> object:
        if isinstance(message, dict):
            return message.get("content", "")
        return getattr(message, "content", "")

    def _messages(self, state: TitleMiddlewareState, message_type: str) -> list[object]:
        return [
            message
            for message in (state.get("messages") or [])
            if self._message_type(message) == message_type
        ]

    def _should_generate(self, state: TitleMiddlewareState) -> bool:
        if state.get("title"):
            return False
        return len(self._messages(state, "human")) == 1 and bool(
            self._messages(state, "ai")
        )

    def _first_message(self, state: TitleMiddlewareState, message_type: str) -> str:
        messages = self._messages(state, message_type)
        if not messages:
            return ""
        return self._service.normalize_content(self._message_content(messages[0]))

    def _messages_for_title(self, state: TitleMiddlewareState) -> tuple[str, str]:
        user_message = self._first_message(state, "human")
        return user_message, self._first_message(state, "ai")

    @staticmethod
    def _runnable_config() -> dict[str, Any]:
        try:
            parent = get_config()
        except RuntimeError:
            parent = {}
        config = {**parent}
        title_config = ConversationTitleService.provider_config()
        config["run_name"] = title_config["run_name"]
        config["tags"] = [*(config.get("tags") or []), *title_config["tags"]]
        return config

    def after_model(
        self,
        state: TitleMiddlewareState,
        runtime: Runtime,
    ) -> dict[str, str] | None:
        del runtime
        if not self._should_generate(state):
            return None
        user_message, assistant_message = self._messages_for_title(state)
        return {"title": self._service.generate(
            user_message,
            assistant_message,
            config=self._runnable_config(),
        )}

    async def aafter_model(
        self,
        state: TitleMiddlewareState,
        runtime: Runtime,
    ) -> dict[str, str] | None:
        del runtime
        if not self._should_generate(state):
            return None
        user_message, assistant_message = self._messages_for_title(state)
        return {"title": await self._service.agenerate(
            user_message,
            assistant_message,
            config=self._runnable_config(),
        )}
