from __future__ import annotations

import json
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
_STEP_MAX_CHARS = 8192


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
        self._tool_callers: dict[str, str] = {}
        self._tool_parent_ids: dict[str, str | None] = {}
        self._parents: dict[str, str | None] = {}
        self._subagent_tasks: dict[str, str] = {}
        self._subagent_step_indexes: dict[str, int] = {}
        self._model_call_index = 0

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, inputs, kwargs
        self._parents[str(run_id)] = _optional_id(parent_run_id)

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, messages, kwargs
        call_id = str(run_id)
        parent_call_id = _optional_id(parent_run_id)
        self._parents[call_id] = parent_call_id
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
                "parent_call_id": parent_call_id,
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
        caller = _identify_caller(tags)
        parent_call_id = self._parents.get(call_id)
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
                    "caller": caller,
                    "parent_call_id": parent_call_id,
                    "latency_ms": latency_ms,
                    "usage": usage.as_dict() if usage is not None else {},
                },
            )
            task_id = self._task_for_call(call_id) if caller.startswith("subagent:") else None
            if task_id is not None:
                await self._emit_subagent_step(
                    task_id,
                    kind="ai",
                    text=_message_text(message),
                    tool_calls=_message_tool_calls(message),
                )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        self._model_started_at.pop(call_id, None)
        call_index = self._model_call_indexes.pop(call_id, None)
        caller = _identify_caller(tags)
        await self._emit(
            "model.error",
            "error",
            content=str(error),
            metadata={
                "call_id": call_id,
                "call_index": call_index,
                "caller": caller,
                "parent_call_id": self._parents.get(call_id) or _optional_id(parent_run_id),
                "error_type": type(error).__name__,
            },
        )

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        tool_name = str((serialized or {}).get("name") or "unknown")
        caller = _identify_caller(tags)
        parent_call_id = _optional_id(parent_run_id)
        self._parents[call_id] = parent_call_id
        self._tool_started_at[call_id] = time.monotonic()
        self._tool_names[call_id] = tool_name
        self._tool_callers[call_id] = caller
        self._tool_parent_ids[call_id] = parent_call_id
        await self._emit(
            "tool.started",
            "tool",
            content=_serialize_value(inputs) if inputs is not None else input_str,
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "caller": caller,
                "parent_call_id": parent_call_id,
            },
        )
        subagent_name = _delegated_subagent_name(tool_name)
        if subagent_name is not None:
            self._subagent_tasks[call_id] = subagent_name
            self._subagent_step_indexes[call_id] = 0
            await self._emit(
                "subagent.start",
                "subagent",
                content={"task_id": call_id, "description": _task_description(inputs, input_str)},
                metadata={
                    "task_id": call_id,
                    "subagent_type": subagent_name,
                    "caller": caller,
                    "parent_call_id": parent_call_id,
                },
            )

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        del kwargs
        call_id = str(run_id)
        started_at = self._tool_started_at.pop(call_id, None)
        tool_name = self._tool_names.pop(call_id, "unknown")
        caller = self._tool_callers.pop(call_id, "unknown")
        parent_call_id = self._tool_parent_ids.pop(call_id, None)
        latency_ms = (
            int((time.monotonic() - started_at) * 1000) if started_at else None
        )
        await self._emit(
            "tool.completed",
            "tool",
            content=_serialize_value(output),
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "caller": caller,
                "parent_call_id": parent_call_id,
                "latency_ms": latency_ms,
            },
        )
        task_id = self._task_for_call(call_id)
        if task_id is not None and call_id != task_id:
            await self._emit_subagent_step(
                task_id,
                kind="tool",
                text=_serialized_text(output),
                tool_name=tool_name,
            )
        subagent_name = self._subagent_tasks.pop(call_id, None)
        if subagent_name is not None:
            self._subagent_step_indexes.pop(call_id, None)
            result_text, result_truncated = _truncate_with_flag(
                _serialized_text(output)
            )
            await self._emit(
                "subagent.end",
                "subagent",
                content={
                    "task_id": call_id,
                    "status": "completed",
                    "result": result_text,
                    "result_truncated": result_truncated,
                },
                metadata={
                    "task_id": call_id,
                    "subagent_type": subagent_name,
                    "latency_ms": latency_ms,
                },
            )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        call_id = str(run_id)
        started_at = self._tool_started_at.pop(call_id, None)
        tool_name = self._tool_names.pop(call_id, "unknown")
        caller = self._tool_callers.pop(call_id, _identify_caller(tags))
        parent_call_id = self._tool_parent_ids.pop(
            call_id, _optional_id(parent_run_id)
        )
        latency_ms = (
            int((time.monotonic() - started_at) * 1000) if started_at else None
        )
        await self._emit(
            "tool.error",
            "error",
            content=str(error),
            metadata={
                "call_id": call_id,
                "tool_name": tool_name,
                "caller": caller,
                "parent_call_id": parent_call_id,
                "error_type": type(error).__name__,
                "latency_ms": latency_ms,
            },
        )
        subagent_name = self._subagent_tasks.pop(call_id, None)
        if subagent_name is not None:
            self._subagent_step_indexes.pop(call_id, None)
            await self._emit(
                "subagent.end",
                "subagent",
                content={
                    "task_id": call_id,
                    "status": (
                        "timed_out" if isinstance(error, TimeoutError) else "failed"
                    ),
                    "error": str(error),
                },
                metadata={
                    "task_id": call_id,
                    "subagent_type": subagent_name,
                    "latency_ms": latency_ms,
                    "error_type": type(error).__name__,
                },
            )

    def _task_for_call(self, call_id: str) -> str | None:
        current: str | None = call_id
        seen: set[str] = set()
        while current is not None and current not in seen:
            if current in self._subagent_tasks:
                return current
            seen.add(current)
            current = self._parents.get(current)
        return None

    async def _emit_subagent_step(
        self,
        task_id: str,
        *,
        kind: str,
        text: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_name: str | None = None,
    ) -> None:
        message_index = self._subagent_step_indexes.get(task_id, 0)
        self._subagent_step_indexes[task_id] = message_index + 1
        bounded_text, truncated = _truncate_with_flag(text)
        content: dict[str, Any] = {
            "task_id": task_id,
            "message_index": message_index,
            "kind": kind,
            "text": bounded_text,
            "truncated": truncated,
        }
        if kind == "tool":
            content["tool_name"] = tool_name
        else:
            content["tool_calls"] = tool_calls or []
        await self._emit(
            "subagent.step",
            "subagent",
            content=content,
            metadata={"task_id": task_id, "message_index": message_index},
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


def _optional_id(value: object) -> str | None:
    return str(value) if value is not None else None


def _delegated_subagent_name(tool_name: str) -> str | None:
    prefix = "delegate_"
    if not tool_name.startswith(prefix) or len(tool_name) == len(prefix):
        return None
    return tool_name.removeprefix(prefix)


def _task_description(inputs: dict[str, Any] | None, input_str: str) -> str:
    if isinstance(inputs, Mapping):
        description = inputs.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
        task = inputs.get("task")
        if isinstance(task, str):
            return task
    return input_str


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part)
    return ""


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for call in getattr(message, "tool_calls", None) or []:
        if isinstance(call, Mapping):
            args = call.get("args")
            serialized_args = _serialized_text(args)
            item: dict[str, Any] = {"name": call.get("name"), "args": args}
            if len(serialized_args) > _STEP_MAX_CHARS:
                item["args"] = serialized_args[:_STEP_MAX_CHARS]
                item["args_truncated"] = True
            result.append(item)
    return result


def _serialized_text(value: Any) -> str:
    serialized = _serialize_value(value)
    if isinstance(serialized, str):
        return serialized
    return json.dumps(serialized, ensure_ascii=False, default=str)


def _truncate_with_flag(value: str) -> tuple[str, bool]:
    if len(value) <= _STEP_MAX_CHARS:
        return value, False
    return value[:_STEP_MAX_CHARS], True


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
