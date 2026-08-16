import asyncio

from langchain_core.messages import ToolMessage

from north.runtime import (
    END_SENTINEL,
    MemoryStreamBridge,
    RunConflictError,
    RunExecutor,
    RunLifecycleHooks,
    RunManager,
    RuntimeExecutionResult,
    RuntimeService,
)
from north.runtime.runs import RunStatus


def test_run_manager_rejects_active_run_for_same_thread():
    manager = RunManager()
    first = manager.create_or_reject(thread_id="thread-1")

    assert first.status == RunStatus.pending

    try:
        manager.create_or_reject(thread_id="thread-1")
        assert False, "Expected active run conflict"
    except RunConflictError:
        pass


def test_run_manager_interrupt_cancels_old_run():
    manager = RunManager()
    first = manager.create_or_reject(thread_id="thread-1")
    second = manager.create_or_reject(thread_id="thread-1", multitask_strategy="interrupt")

    assert first.abort_event.is_set()
    assert first.status == RunStatus.interrupted
    assert second.status == RunStatus.pending


def test_memory_stream_bridge_replays_after_cursor_and_ends():
    asyncio.run(_assert_memory_stream_bridge_replay())


async def _assert_memory_stream_bridge_replay():
    bridge = MemoryStreamBridge()
    await bridge.publish("run-1", "first", {"value": 1})
    await bridge.publish("run-1", "second", {"value": 2})
    await bridge.publish_end("run-1")

    events = [event async for event in bridge.subscribe("run-1", last_event_id="0-0")]

    assert [(event.event, event.data) for event in events] == [
        ("second", {"value": 2}),
        (END_SENTINEL.event, None),
    ]


def test_memory_stream_bridge_reports_unknown_cursor_gap():
    asyncio.run(_assert_memory_unknown_cursor_gap())


async def _assert_memory_unknown_cursor_gap():
    bridge = MemoryStreamBridge()
    await bridge.publish("run-1", "values", {"value": 1})
    await bridge.publish_end("run-1")

    events = [
        event
        async for event in bridge.subscribe("run-1", last_event_id="0-999")
    ]

    assert events[0].event == "__replay_gap__"
    assert events[1].data == {"value": 1}
    assert events[-1] is END_SENTINEL


def test_run_executor_publishes_canonical_messages_and_finalizes_before_end():
    asyncio.run(_assert_run_executor_success())


async def _assert_run_executor_success():
    class StubAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            assert stream_mode == ["values", "messages"]
            yield (
                ("subgraph:agent",),
                "messages",
                ({"type": "AIMessageChunk", "content": "好"}, {}),
            )
            yield ("values", {"messages": [], "value": graph_input["value"]})

    manager = RunManager()
    bridge = MemoryStreamBridge()
    record = manager.create(thread_id="thread-1", run_id="run-1")
    observed = []

    async def completed(result):
        observed.append(("completed", result.values["value"]))
        await bridge.publish("run-1", "product_completed", result.values)

    result = await RunExecutor(bridge, manager).execute(
        record,
        agent_factory=StubAgent,
        graph_input={"value": 1},
        lifecycle_hooks=RunLifecycleHooks(on_completed=completed),
    )
    events = [event async for event in bridge.subscribe("run-1")]

    assert isinstance(result, RuntimeExecutionResult)
    assert result.values["value"] == 1
    assert result.clarification is None
    assert manager.get("run-1").status == RunStatus.success
    assert [event.event for event in events] == [
        "metadata",
        "messages-tuple",
        "product_completed",
        END_SENTINEL.event,
    ]
    assert observed == [("completed", 1)]
    assert events[1].namespace == ("subgraph:agent",)


def test_run_executor_emits_typed_clarification_result():
    asyncio.run(_assert_typed_clarification_result())


async def _assert_typed_clarification_result():
    class StubAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            del graph_input, config, context, stream_mode
            yield (
                "values",
                {
                    "messages": [],
                    "clarification_request": {
                        "question": "When should it start?",
                        "response_kind": "single_choice",
                        "options": ["09:00", "14:00"],
                    },
                },
            )

    observed = []

    async def completed(result):
        observed.append(result)

    result = await RunExecutor(MemoryStreamBridge()).execute(
        RunManager().create(thread_id="thread-1", run_id="run-clarification"),
        agent_factory=StubAgent,
        graph_input={},
        lifecycle_hooks=RunLifecycleHooks(on_completed=completed),
    )

    assert result.clarification is not None
    assert result.clarification.question == "When should it start?"
    assert result.clarification.response_kind == "single_choice"
    assert result.clarification.options == ("09:00", "14:00")
    assert observed == [result]


def test_run_executor_can_leave_lifecycle_publication_to_host():
    asyncio.run(_assert_run_executor_host_lifecycle())


async def _assert_run_executor_host_lifecycle():
    class StubAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            del graph_input, config, context
            assert stream_mode == ["values", "messages"]
            yield ("messages", ({"type": "AIMessageChunk", "content": "好"}, {}))
            yield ("values", {"messages": []})

    bridge = MemoryStreamBridge()
    record = RunManager().create(thread_id="thread-1", run_id="run-host")
    await RunExecutor(bridge).execute(
        record,
        agent_factory=StubAgent,
        graph_input={},
        publish_modes=(),
        publish_lifecycle=False,
    )
    await bridge.publish_end("run-host")
    events = [event async for event in bridge.subscribe("run-host")]

    assert [event.event for event in events] == [END_SENTINEL.event]


def test_run_executor_preserves_tool_message_artifact_in_canonical_stream():
    asyncio.run(_assert_tool_message_artifact_stream())


async def _assert_tool_message_artifact_stream():
    artifact = {
        "tool_call_id": "tool-1",
        "operation": "calendar_entry_created",
        "item": {"kind": "calendar", "value": {"id": "calendar-1", "title": "跳舞"}},
    }

    class StubAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            del graph_input, config, context
            assert stream_mode == ["values", "messages"]
            yield (
                "messages",
                (
                    ToolMessage(
                        content='{"type":"calendar_entry_created","id":"calendar-1"}',
                        artifact=artifact,
                        name="create_calendar_entry",
                        tool_call_id="tool-1",
                    ),
                    {"langgraph_node": "tools"},
                ),
            )
            yield ("values", {"messages": []})

    bridge = MemoryStreamBridge()
    record = RunManager().create(thread_id="thread-1", run_id="run-artifact")
    await RunExecutor(bridge).execute(
        record,
        agent_factory=StubAgent,
        graph_input={},
    )
    events = [event async for event in bridge.subscribe("run-artifact")]

    message_event = next(event for event in events if event.event == "messages-tuple")
    assert message_event.data[0]["content"] == (
        '{"type":"calendar_entry_created","id":"calendar-1"}'
    )
    assert message_event.data[0]["artifact"] == artifact


def test_run_executor_persists_error_before_error_event_and_end():
    asyncio.run(_assert_run_executor_error())


async def _assert_run_executor_error():
    class FailingAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            del graph_input, config, context, stream_mode
            raise ValueError("boom")
            yield

    manager = RunManager()
    bridge = MemoryStreamBridge()
    record = manager.create(thread_id="thread-1", run_id="run-1")

    async def failed(exc):
        await bridge.publish("run-1", "product_failed", {"message": str(exc)})

    try:
        await RunExecutor(bridge, manager).execute(
            record,
            agent_factory=FailingAgent,
            graph_input={},
            lifecycle_hooks=RunLifecycleHooks(on_error=failed),
        )
        assert False, "Expected executor failure"
    except ValueError as exc:
        assert str(exc) == "boom"

    events = [event async for event in bridge.subscribe("run-1")]
    assert manager.get("run-1").status == RunStatus.error
    assert [event.event for event in events] == [
        "metadata",
        "product_failed",
        "error",
        END_SENTINEL.event,
    ]


def test_run_executor_calls_error_lifecycle_when_metadata_publish_fails():
    asyncio.run(_assert_metadata_publish_failure())


async def _assert_metadata_publish_failure():
    class MetadataFailingBridge(MemoryStreamBridge):
        async def publish(self, run_id, event, data):
            if event == "metadata":
                raise ConnectionError("bridge unavailable")
            await super().publish(run_id, event, data)

    manager = RunManager()
    bridge = MetadataFailingBridge()
    record = manager.create(thread_id="thread-1", run_id="run-1")
    failures = []

    async def failed(exc):
        failures.append(str(exc))

    try:
        await RunExecutor(bridge, manager).execute(
            record,
            agent_factory=lambda: object(),
            graph_input={},
            lifecycle_hooks=RunLifecycleHooks(on_error=failed),
        )
        assert False, "Expected bridge failure"
    except ConnectionError:
        pass

    events = [event async for event in bridge.subscribe("run-1")]
    assert failures == ["bridge unavailable"]
    assert [event.event for event in events] == ["error", END_SENTINEL.event]


def test_runtime_service_uses_executor_and_supports_cancellation():
    asyncio.run(_assert_runtime_service_cancel())


async def _assert_runtime_service_cancel():
    started = asyncio.Event()

    class SlowAgent:
        async def astream(self, graph_input, config=None, context=None, stream_mode=None):
            del graph_input, config, context, stream_mode
            started.set()
            while True:
                await asyncio.sleep(1)
                yield ("values", {})

    service = RuntimeService()
    record = await service.start_run(
        thread_id="thread-1",
        agent_factory=SlowAgent,
        graph_input={},
    )
    await started.wait()
    assert service.cancel_run(record.run_id)

    try:
        await record.task
    except asyncio.CancelledError:
        pass
    events = [event async for event in service.stream_run(record.run_id)]

    assert events[-1] is END_SENTINEL
    assert service.run_manager.get(record.run_id).status == RunStatus.interrupted
