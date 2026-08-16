from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .events import RuntimeEventSink
from .invoke import RuntimeStreamEvent, normalize_stream_chunk, with_runtime_journal
from .results import RuntimeExecutionResult, clarification_from_values
from .runs import RunManager, RunRecord, RunStatus
from .stream_bridge import StreamBridge

StreamObserver = Callable[[RuntimeStreamEvent], Awaitable[None]]
LifecycleCallback = Callable[..., Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RunLifecycleHooks:
    """Host persistence callbacks that must settle before a run stream ends."""

    on_completed: LifecycleCallback | None = None
    on_error: LifecycleCallback | None = None
    on_interrupted: LifecycleCallback | None = None


class RunExecutor:
    """The sole production owner of the agent ``astream`` execution loop."""

    def __init__(self, bridge: StreamBridge, run_manager: RunManager | None = None) -> None:
        self._bridge = bridge
        self._run_manager = run_manager

    async def execute(
        self,
        record: RunRecord,
        *,
        agent_factory: Callable[[], Any],
        graph_input: dict[str, Any],
        config: Any | None = None,
        context: dict[str, Any] | None = None,
        event_sink: RuntimeEventSink | None = None,
        stream_observer: StreamObserver | None = None,
        lifecycle_hooks: RunLifecycleHooks | None = None,
        stream_modes: Sequence[str] = ("values", "messages"),
        publish_modes: Sequence[str] = ("messages",),
        publish_lifecycle: bool = True,
    ) -> RuntimeExecutionResult:
        requested_modes = tuple(stream_modes)
        published_modes = frozenset(publish_modes)
        if not requested_modes:
            raise ValueError("stream_modes must contain at least one mode")
        if not published_modes.issubset(requested_modes):
            raise ValueError("publish_modes must be a subset of stream_modes")

        hooks = lifecycle_hooks or RunLifecycleHooks()
        latest_values: Any = {}
        try:
            self._set_status(record.run_id, RunStatus.running)
            if publish_lifecycle:
                await self._bridge.publish(
                    record.run_id,
                    "metadata",
                    {"run_id": record.run_id, "thread_id": record.thread_id},
                )
            agent = agent_factory()
            astream = getattr(agent, "astream", None)
            if not callable(astream):
                raise TypeError("Agent does not expose astream")

            resolved_config = with_runtime_journal(config, event_sink)
            async for raw_chunk in astream(
                graph_input,
                config=resolved_config,
                context=context,
                stream_mode=list(requested_modes),
            ):
                if record.abort_event.is_set():
                    raise asyncio.CancelledError
                event = normalize_stream_chunk(raw_chunk, requested_modes)
                if stream_observer is not None:
                    await stream_observer(event)
                if event.mode in published_modes:
                    await self._bridge.publish(
                        record.run_id,
                        _bridge_event_name(event.mode),
                        event.data,
                        namespace=event.namespace,
                    )
                if event.mode == "values":
                    latest_values = event.data

            if record.abort_event.is_set():
                raise asyncio.CancelledError
            result = RuntimeExecutionResult(
                values=latest_values,
                clarification=clarification_from_values(latest_values),
            )
            if hooks.on_completed is not None:
                await hooks.on_completed(result)
            self._set_status(record.run_id, RunStatus.success)
            return result
        except asyncio.CancelledError:
            self._set_status(record.run_id, RunStatus.interrupted)
            if hooks.on_interrupted is not None:
                await hooks.on_interrupted()
            raise
        except Exception as exc:
            self._set_status(record.run_id, RunStatus.error, error=str(exc))
            if hooks.on_error is not None:
                await hooks.on_error(exc)
            if publish_lifecycle:
                await self._bridge.publish(
                    record.run_id,
                    "error",
                    {"message": str(exc), "error_type": type(exc).__name__},
                )
            raise
        finally:
            if publish_lifecycle:
                await self._bridge.publish_end(record.run_id)

    def _set_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
    ) -> None:
        if self._run_manager is not None:
            self._run_manager.set_status(run_id, status, error=error)


def _bridge_event_name(mode: str) -> str:
    if mode == "messages":
        return "messages-tuple"
    return mode
