from __future__ import annotations

import logging
import re
from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.config import get_config
from langgraph.constants import TAG_NOSTREAM
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class TitleMiddlewareState(AgentState):
    title: NotRequired[str | None]


class TitleMiddleware(AgentMiddleware[TitleMiddlewareState]):
    """Generate one thread title after the first model exchange."""

    state_schema = TitleMiddlewareState

    def __init__(
        self,
        *,
        model: Any | None = None,
        max_chars: int = 60,
        prompt_template: str | None = None,
    ) -> None:
        super().__init__()
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        self._model = model
        self._max_chars = max_chars
        self._prompt_template = prompt_template or (
            "请为下面这轮对话生成一个简洁、具体的中文标题。"
            "标题只概括用户要处理的事项，不回答问题，不添加事实，不使用引号，"
            "不要输出解释或 Markdown，最多 {max_chars} 个字符。\n\n"
            "用户：{user_message}\n\n助手：{assistant_message}"
        )

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

    @classmethod
    def _normalize_content(cls, content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [cls._normalize_content(item) for item in content]
            return "\n".join(part for part in parts if part)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
            nested = content.get("content")
            if nested is not None:
                return cls._normalize_content(nested)
        return ""

    @staticmethod
    def _strip_thinking(text: str) -> str:
        return re.sub(
            r"<think>[\s\S]*?</think>",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

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
        return self._normalize_content(self._message_content(messages[0]))

    def _fallback_title(self, user_message: str) -> str:
        normalized = " ".join(user_message.split())
        if not normalized:
            return "New Conversation"
        if len(normalized) <= self._max_chars:
            return normalized
        ellipsis = "..."
        return normalized[: self._max_chars - len(ellipsis)].rstrip() + ellipsis

    def _parse_title(self, content: object) -> str:
        title = self._strip_thinking(self._normalize_content(content))
        title = title.strip().strip('"').strip("'").strip()
        return title[: self._max_chars].rstrip()

    def _prompt(self, state: TitleMiddlewareState) -> tuple[str, str]:
        user_message = self._first_message(state, "human")
        assistant_message = self._strip_thinking(self._first_message(state, "ai"))
        return (
            self._prompt_template.format(
                max_chars=self._max_chars,
                user_message=user_message[:500],
                assistant_message=assistant_message[:500],
            ),
            user_message,
        )

    @staticmethod
    def _runnable_config() -> dict[str, Any]:
        try:
            parent = get_config()
        except RuntimeError:
            parent = {}
        config = {**parent}
        config["run_name"] = "title_agent"
        config["tags"] = [
            *(config.get("tags") or []),
            "middleware:title",
            TAG_NOSTREAM,
        ]
        return config

    def after_model(
        self,
        state: TitleMiddlewareState,
        runtime: Runtime,
    ) -> dict[str, str] | None:
        del runtime
        if not self._should_generate(state):
            return None
        prompt, user_message = self._prompt(state)
        if self._model is None:
            return {"title": self._fallback_title(user_message)}
        try:
            response = self._model.invoke(prompt, config=self._runnable_config())
            title = self._parse_title(response.content)
            if title:
                return {"title": title}
        except Exception:
            logger.debug("Title generation failed; using local fallback", exc_info=True)
        return {"title": self._fallback_title(user_message)}

    async def aafter_model(
        self,
        state: TitleMiddlewareState,
        runtime: Runtime,
    ) -> dict[str, str] | None:
        del runtime
        if not self._should_generate(state):
            return None
        prompt, user_message = self._prompt(state)
        if self._model is None:
            return {"title": self._fallback_title(user_message)}
        try:
            response = await self._model.ainvoke(
                prompt,
                config=self._runnable_config(),
            )
            title = self._parse_title(response.content)
            if title:
                return {"title": title}
        except Exception:
            logger.debug("Title generation failed; using local fallback", exc_info=True)
        return {"title": self._fallback_title(user_message)}
