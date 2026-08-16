import asyncio
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import AIMessage
from north import (
    RuntimeEvent,
    RuntimeJournal,
    RuntimeUsageAccumulator,
    invoke_agent_once,
    normalize_token_usage,
)


def test_runtime_journal_emits_correlated_model_and_tool_events() -> None:
    asyncio.run(_assert_runtime_journal_events())


async def _assert_runtime_journal_events() -> None:
    events: list[RuntimeEvent] = []

    async def sink(event: RuntimeEvent) -> None:
        events.append(event)

    journal = RuntimeJournal(sink)
    model_run_id = uuid4()
    tool_run_id = uuid4()
    await journal.on_chat_model_start({}, [[]], run_id=model_run_id, tags=["lead_agent"])
    await journal.on_llm_end(
        SimpleNamespace(
            generations=[
                [
                    SimpleNamespace(
                        message=AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "id": "call-1",
                                    "name": "create_task",
                                    "args": {"title": "提交周报"},
                                }
                            ],
                            usage_metadata={
                                "input_tokens": 10,
                                "output_tokens": 4,
                                "total_tokens": 14,
                                "input_token_details": {"cache_read": 8},
                            },
                        )
                    )
                ]
            ]
        ),
        run_id=model_run_id,
        tags=["lead_agent"],
    )
    await journal.on_tool_start(
        {"name": "create_task"},
        "",
        run_id=tool_run_id,
        inputs={"title": "提交周报"},
    )
    await journal.on_tool_end(
        {"task_id": "task-1"},
        run_id=tool_run_id,
    )

    assert [event.event_type for event in events] == [
        "model.started",
        "model.completed",
        "tool.started",
        "tool.completed",
    ]
    assert events[0].metadata["caller"] == "lead_agent"
    assert events[1].metadata["usage"]["total_tokens"] == 14
    assert events[1].metadata["usage"]["cached_input_tokens"] == 8
    assert events[1].metadata["call_index"] == 1
    assert events[1].content["tool_calls"][0]["name"] == "create_task"
    assert events[2].metadata["call_id"] == str(tool_run_id)
    assert events[2].content == {"title": "提交周报"}
    assert events[3].metadata["call_id"] == str(tool_run_id)
    assert events[3].metadata["tool_name"] == "create_task"


def test_normalizes_provider_usage_aliases_and_derives_total() -> None:
    usage = normalize_token_usage(
        {"token_usage": {"prompt_tokens": 12, "completion_tokens": 3}}
    )

    assert usage is not None
    assert usage.as_dict() == {
        "input_tokens": 12,
        "output_tokens": 3,
        "total_tokens": 15,
    }


def test_runtime_journal_attributes_subagent_steps_to_delegation() -> None:
    asyncio.run(_assert_subagent_event_lineage())


async def _assert_subagent_event_lineage() -> None:
    events: list[RuntimeEvent] = []

    async def sink(event: RuntimeEvent) -> None:
        events.append(event)

    journal = RuntimeJournal(sink)
    lead_chain_id = uuid4()
    task_id = uuid4()
    child_chain_id = uuid4()
    child_model_id = uuid4()
    child_tool_id = uuid4()

    await journal.on_chain_start({}, {}, run_id=lead_chain_id)
    await journal.on_tool_start(
        {"name": "delegate_case_analyst"},
        "",
        run_id=task_id,
        parent_run_id=lead_chain_id,
        tags=["lead_agent"],
        inputs={"task": "整理案件事实"},
    )
    await journal.on_chain_start(
        {},
        {},
        run_id=child_chain_id,
        parent_run_id=task_id,
    )
    await journal.on_chat_model_start(
        {},
        [[]],
        run_id=child_model_id,
        parent_run_id=child_chain_id,
        tags=["subagent:case_analyst"],
    )
    await journal.on_llm_end(
        SimpleNamespace(
            generations=[
                [SimpleNamespace(message=AIMessage(content="已识别案件事实。"))]
            ]
        ),
        run_id=child_model_id,
        tags=["subagent:case_analyst"],
    )
    await journal.on_tool_start(
        {"name": "search_case_materials"},
        "",
        run_id=child_tool_id,
        parent_run_id=child_chain_id,
        tags=["subagent:case_analyst"],
        inputs={"query": "解除通知"},
    )
    await journal.on_tool_end([{"reference": "M1:C1"}], run_id=child_tool_id)
    await journal.on_tool_end(
        {"subagent": "case_analyst", "result": {"facts": 1}},
        run_id=task_id,
    )

    subagent_events = [event for event in events if event.category == "subagent"]
    assert [event.event_type for event in subagent_events] == [
        "subagent.start",
        "subagent.step",
        "subagent.step",
        "subagent.end",
    ]
    assert subagent_events[0].content == {
        "task_id": str(task_id),
        "description": "整理案件事实",
    }
    assert [event.content["message_index"] for event in subagent_events[1:3]] == [
        0,
        1,
    ]
    assert subagent_events[1].content["kind"] == "ai"
    assert subagent_events[2].content["kind"] == "tool"
    assert subagent_events[2].content["tool_name"] == "search_case_materials"
    assert subagent_events[3].content["status"] == "completed"
    child_tool_start = next(
        event
        for event in events
        if event.event_type == "tool.started"
        and event.metadata["tool_name"] == "search_case_materials"
    )
    assert child_tool_start.metadata["caller"] == "subagent:case_analyst"
    assert child_tool_start.metadata["parent_call_id"] == str(child_chain_id)


def test_normalizes_cached_input_token_details_without_inventing_zero() -> None:
    cached = normalize_token_usage(
        {
            "input_tokens": 100,
            "output_tokens": 5,
            "input_token_details": {"cache_read": 80},
        }
    )
    omitted = normalize_token_usage({"input_tokens": 100, "output_tokens": 5})

    assert cached is not None
    assert cached.cached_input_tokens == 80
    assert cached.as_dict()["cached_input_tokens"] == 80
    assert omitted is not None
    assert omitted.cached_input_tokens is None
    assert "cached_input_tokens" not in omitted.as_dict()


def test_runtime_usage_accumulator_sums_each_model_call_once() -> None:
    asyncio.run(_assert_runtime_usage_accumulator())


async def _assert_runtime_usage_accumulator() -> None:
    accumulator = RuntimeUsageAccumulator()
    first = RuntimeEvent(
        "model.completed",
        "model",
        metadata={
            "call_id": "call-1",
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        },
    )
    await accumulator(first)
    await accumulator(first)
    await accumulator(
        RuntimeEvent(
            "model.completed",
            "model",
            metadata={
                "call_id": "call-2",
                "usage": {"prompt_tokens": 7, "completion_tokens": 1},
            },
        )
    )

    assert accumulator.total is not None
    assert accumulator.total.as_dict() == {
        "input_tokens": 17,
        "output_tokens": 3,
        "total_tokens": 20,
    }
    assert [call["call_id"] for call in accumulator.calls] == ["call-1", "call-2"]


def test_invoke_agent_once_merges_runtime_journal_with_existing_callbacks() -> None:
    asyncio.run(_assert_invoke_agent_once_merges_callbacks())


async def _assert_invoke_agent_once_merges_callbacks() -> None:
    existing_callback = object()
    captured = {}

    class StubAgent:
        async def ainvoke(self, graph_input, *, config=None, context=None):
            captured.update(graph_input=graph_input, config=config, context=context)
            return {"ok": True}

    async def sink(event: RuntimeEvent) -> None:
        del event

    result = await invoke_agent_once(
        agent_factory=StubAgent,
        graph_input={"messages": []},
        config={"callbacks": [existing_callback], "configurable": {"thread_id": "thread-1"}},
        context={"run_id": "run-1"},
        event_sink=sink,
    )

    assert result == {"ok": True}
    assert captured["config"]["callbacks"][0] is existing_callback
    assert isinstance(captured["config"]["callbacks"][1], RuntimeJournal)
    assert captured["config"]["configurable"] == {"thread_id": "thread-1"}
    assert captured["context"] == {"run_id": "run-1"}
