from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from langgraph.constants import TAG_NOSTREAM

logger = logging.getLogger(__name__)


class TitleProvider(Protocol):
    def invoke(self, input: str, *, config: dict[str, Any]) -> Any:
        ...

    async def ainvoke(self, input: str, *, config: dict[str, Any]) -> Any:
        ...


class ConversationTitleService:
    """Product-neutral title rules around a host-selected model provider."""

    def __init__(
        self,
        *,
        provider: TitleProvider | None,
        max_chars: int = 60,
        prompt_template: str | None = None,
    ) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        self._provider = provider
        self._max_chars = max_chars
        self._prompt_template = prompt_template or (
            "请为下面这轮对话生成一个简洁、具体的中文标题。"
            "标题只概括用户要处理的事项，不回答问题，不添加事实，不使用引号，"
            "不要输出解释或 Markdown，最多 {max_chars} 个字符。\n\n"
            "用户：{user_message}\n\n助手：{assistant_message}"
        )

    def _prompt(self, user_message: str, assistant_message: str) -> str:
        return self._prompt_template.format(
            max_chars=self._max_chars,
            user_message=user_message[:500],
            assistant_message=self._strip_thinking(assistant_message)[:500],
        )

    def _fallback(self, user_message: str) -> str:
        normalized = " ".join(user_message.split())
        if not normalized:
            return "New Conversation"
        if len(normalized) <= self._max_chars:
            return normalized
        ellipsis = "..."
        return normalized[: self._max_chars - len(ellipsis)].rstrip() + ellipsis

    def _parse(self, content: object) -> str:
        title = self._strip_thinking(self.normalize_content(content))
        return title.strip().strip('"').strip("'").strip()[: self._max_chars].rstrip()

    def generate(self, user_message: str, assistant_message: str, *, config: dict[str, Any]) -> str:
        if self._provider is None:
            return self._fallback(user_message)
        try:
            response = self._provider.invoke(
                self._prompt(user_message, assistant_message),
                config=config,
            )
            title = self._parse(getattr(response, "content", response))
            if title:
                return title
        except Exception:
            logger.debug("Title generation failed; using local fallback", exc_info=True)
        return self._fallback(user_message)

    async def agenerate(
        self,
        user_message: str,
        assistant_message: str,
        *,
        config: dict[str, Any],
    ) -> str:
        if self._provider is None:
            return self._fallback(user_message)
        try:
            response = await self._provider.ainvoke(
                self._prompt(user_message, assistant_message),
                config=config,
            )
            title = self._parse(getattr(response, "content", response))
            if title:
                return title
        except Exception:
            logger.debug("Title generation failed; using local fallback", exc_info=True)
        return self._fallback(user_message)

    @staticmethod
    def _strip_thinking(text: str) -> str:
        return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    @classmethod
    def normalize_content(cls, content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part
                for part in (cls.normalize_content(item) for item in content)
                if part
            )
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
            nested = content.get("content")
            if nested is not None:
                return cls.normalize_content(nested)
        return ""

    @staticmethod
    def provider_config() -> dict[str, Any]:
        return {"run_name": "title_agent", "tags": ["service:title", TAG_NOSTREAM]}


__all__ = ["ConversationTitleService", "TitleProvider"]
