from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    event_type: str
    category: str
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


RuntimeEventSink = Callable[[RuntimeEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None

    def as_dict(self) -> dict[str, int]:
        result = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.cached_input_tokens is not None:
            result["cached_input_tokens"] = self.cached_input_tokens
        return result


class RuntimeUsageAccumulator:
    """Collect normalized token usage once per model call from runtime events."""

    def __init__(self) -> None:
        self._calls: dict[str, TokenUsage] = {}

    async def __call__(self, event: RuntimeEvent) -> None:
        if event.event_type != "model.completed":
            return
        call_id = event.metadata.get("call_id")
        usage = normalize_token_usage(event.metadata.get("usage"))
        if not isinstance(call_id, str) or not call_id or usage is None:
            return
        self._calls.setdefault(call_id, usage)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return [
            {"call_id": call_id, **usage.as_dict()}
            for call_id, usage in self._calls.items()
        ]

    @property
    def total(self) -> TokenUsage | None:
        if not self._calls:
            return None
        return TokenUsage(
            input_tokens=sum(usage.input_tokens for usage in self._calls.values()),
            output_tokens=sum(usage.output_tokens for usage in self._calls.values()),
            total_tokens=sum(usage.total_tokens for usage in self._calls.values()),
            cached_input_tokens=(
                sum(usage.cached_input_tokens for usage in self._calls.values())
                if all(usage.cached_input_tokens is not None for usage in self._calls.values())
                else None
            ),
        )


class RuntimeJournal(AsyncCallbackHandler):
    """Translate LangChain callbacks into product-neutral runtime events."""

    def __init__(self, sink: RuntimeEventSink) -> None:
        self._sink = sink
        self._model_started_at: dict[str, float] = {}
        self._model_call_indexes: dict[str, int] = {}
        self._tool_started_at: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._model_call_index = 0

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, messages, kwargs
        call_id = str(run_id)
        self._model_started_at[call_id] = time.monotonic()
        self._model_call_index += 1
        self._model_call_indexes[call_id] = self._model_call_index
        await self._emit(
            "model.started",
            "model",
            metadata={
                "call_id": call_id,
                "call_index": self._model_call_index,
                "caller": _identify_caller(tags),
            },
        )

    async def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        started_at = self._model_started_at.pop(call_id, None)
        call_index = self._model_call_indexes.pop(call_id, None)
        latency_ms = int((time.monotonic() - started_at) * 1000) if started_at else None
        response_usage = _response_usage(response)
        for index, message in enumerate(_response_messages(response)):
            usage = normalize_token_usage(
                getattr(message, "usage_metadata", None),
                getattr(message, "response_metadata", None),
                response_usage if index == 0 else None,
            )
            await self._emit(
                "model.completed",
                "model",
                content=_serialize_value(message),
                metadata={
                    "call_id": call_id,
                    "call_index": call_index,
                    "caller": _identify_caller(tags),
                    "latency_ms": latency_ms,
                    "usage": usage.as_dict() if usage is not None else {},
                },
            )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        self._model_started_at.pop(call_id, None)
        call_index = self._model_call_indexes.pop(call_id, None)
        await self._emit(
            "model.error",
            "error",
            content=str(error),
            metadata={
                "call_id": call_id,
                "call_index": call_index,
                "error_type": type(error).__name__,
            },
        )

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        tool_name = str((serialized or {}).get("name") or "unknown")
        self._tool_started_at[call_id] = time.monotonic()
        self._tool_names[call_id] = tool_name
        await self._emit(
            "tool.started",
            "tool",
            content=_serialize_value(inputs) if inputs is not None else input_str,
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
            },
        )

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        del kwargs
        call_id = str(run_id)
        started_at = self._tool_started_at.pop(call_id, None)
        tool_name = self._tool_names.pop(call_id, "unknown")
        await self._emit(
            "tool.completed",
            "tool",
            content=_serialize_value(output),
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "latency_ms": int((time.monotonic() - started_at) * 1000)
                if started_at
                else None,
            },
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        started_at = self._tool_started_at.pop(call_id, None)
        tool_name = self._tool_names.pop(call_id, "unknown")
        await self._emit(
            "tool.error",
            "error",
            content=str(error),
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "error_type": type(error).__name__,
                "latency_ms": int((time.monotonic() - started_at) * 1000)
                if started_at
                else None,
            },
        )

    async def _emit(
        self,
        event_type: str,
        category: str,
        *,
        content: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._sink(
            RuntimeEvent(
                event_type=event_type,
                category=category,
                content=content,
                metadata=metadata or {},
            )
        )


def _identify_caller(tags: list[str] | None) -> str:
    for tag in tags or []:
        if tag == "lead_agent" or tag.startswith(("subagent:", "middleware:")):
            return tag
    return "unknown"


def _response_messages(response: Any) -> list[Any]:
    messages: list[Any] = []
    for generation in getattr(response, "generations", []) or []:
        for item in generation:
            message = getattr(item, "message", None)
            if message is not None:
                messages.append(message)
    return messages


def _response_usage(response: Any) -> Any:
    llm_output = getattr(response, "llm_output", None)
    if not isinstance(llm_output, Mapping):
        return None
    return llm_output.get("token_usage") or llm_output.get("usage")


def normalize_token_usage(*candidates: Any) -> TokenUsage | None:
    """Normalize common LangChain and provider token-usage field names."""

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        nested = candidate.get("token_usage") or candidate.get("usage")
        sources = (candidate, nested) if isinstance(nested, Mapping) else (candidate,)
        for source in sources:
            input_tokens = _token_count(source, "input_tokens", "prompt_tokens")
            output_tokens = _token_count(source, "output_tokens", "completion_tokens")
            total_tokens = _token_count(source, "total_tokens")
            if input_tokens is None and output_tokens is None and total_tokens is None:
                continue
            resolved_input = input_tokens or 0
            resolved_output = output_tokens or 0
            return TokenUsage(
                input_tokens=resolved_input,
                output_tokens=resolved_output,
                total_tokens=(
                    total_tokens
                    if total_tokens is not None
                    else resolved_input + resolved_output
                ),
                cached_input_tokens=_cached_input_tokens(source),
            )
    return None


def _token_count(source: Mapping[Any, Any], *names: str) -> int | None:
    for name in names:
        value = source.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _cached_input_tokens(source: Mapping[Any, Any]) -> int | None:
    direct = _token_count(
        source,
        "cached_input_tokens",
        "cached_prompt_tokens",
        "cached_tokens",
    )
    if direct is not None:
        return direct
    for details_name, token_name in (
        ("input_token_details", "cache_read"),
        ("prompt_tokens_details", "cached_tokens"),
    ):
        details = source.get(details_name)
        if isinstance(details, Mapping):
            value = _token_count(details, token_name)
            if value is not None:
                return value
    return None


def _serialize_value(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
