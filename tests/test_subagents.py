from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from north.subagents import AgentDefinition, create_subagent_tool


class StubAgent:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def ainvoke(self, graph_input, *, config=None, context=None):
        self.calls.append(
            {
                "graph_input": graph_input,
                "config": config,
                "context": context,
            }
        )
        return self.result


def runtime(*, config=None, context=None):
    return SimpleNamespace(config=config or {}, context=context or {})


def test_agent_definition_normalizes_public_identity() -> None:
    spec = AgentDefinition(
        name=" case_analyst ",
        description=" Frame one case. ",
        system_prompt=" Analyze only grounded facts. ",
        skills=("case-framing", "case-framing", ""),
    )

    assert spec.name == "case_analyst"
    assert spec.tool_name == "delegate_case_analyst"
    assert spec.description == "Frame one case."
    assert spec.skills == ("case-framing",)


@pytest.mark.parametrize("name", ["CaseAnalyst", "case-analyst", "1analyst", ""])
def test_agent_definition_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(ValueError, match="agent definition name"):
        AgentDefinition(
            name=name,
            description="Frame one case.",
            system_prompt="Analyze grounded facts.",
        )


def test_delegation_tool_propagates_parent_runtime_without_checkpoint() -> None:
    callback = object()
    agent = StubAgent(
        {"messages": [AIMessage(content="争议焦点已整理。")]}
    )
    spec = AgentDefinition(
        name="case_analyst",
        description="Frame one legal case.",
        system_prompt="Analyze grounded facts.",
        recursion_limit=12,
    )
    tool = create_subagent_tool(spec, lambda _definition: agent)

    result = asyncio.run(
        tool.coroutine(
            description="梳理案件事实",
            task="整理本轮案件事实",
            runtime=runtime(
                config={
                    "callbacks": [callback],
                    "tags": ["lead_agent", "request:one"],
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_id": "checkpoint-1",
                    },
                },
                context={"run_id": "run-1"},
            ),
        )
    )

    assert json.loads(result) == {
        "subagent": "case_analyst",
        "result": "争议焦点已整理。",
    }
    assert set(tool.tool_call_schema.model_json_schema()["properties"]) == {
        "description",
        "task",
    }
    call = agent.calls[0]
    assert call["graph_input"]["messages"][0].content == "整理本轮案件事实"
    assert call["config"]["callbacks"] == [callback]
    assert call["config"]["tags"] == ["request:one", "subagent:case_analyst"]
    assert call["config"]["recursion_limit"] == 12
    assert call["config"]["configurable"] == {"thread_id": "thread-1"}
    assert call["context"] == {"run_id": "run-1"}


def test_delegation_tool_returns_structured_response() -> None:
    agent = StubAgent(
        {
            "messages": [AIMessage(content="internal draft")],
            "structured_response": {
                "issues": ["劳动合同解除是否合法"],
                "research_questions": ["违法解除赔偿金标准"],
            },
        }
    )
    spec = AgentDefinition(
        name="case_analyst",
        description="Frame one legal case.",
        system_prompt="Analyze grounded facts.",
        result_schema=dict,
    )

    result = asyncio.run(
        create_subagent_tool(spec, lambda _definition: agent).coroutine(
            description="梳理案件事实",
            task="整理案件",
            runtime=runtime(),
        )
    )

    assert json.loads(result)["result"] == {
        "issues": ["劳动合同解除是否合法"],
        "research_questions": ["违法解除赔偿金标准"],
    }


def test_delegation_tool_processes_structured_result_with_runtime() -> None:
    agent = StubAgent(
        {
            "messages": [AIMessage(content="internal draft")],
            "structured_response": {"intent": "legal_question"},
        }
    )
    observed = []

    async def process(result, tool_runtime):
        observed.append((result, tool_runtime.context))
        return {"assessment": result, "response_contract": {"answer_first": True}}

    spec = AgentDefinition(
        name="case_analyst",
        description="Frame one legal case.",
        system_prompt="Analyze grounded facts.",
        result_schema=dict,
        result_processor=process,
    )

    result = asyncio.run(
        create_subagent_tool(spec, lambda _definition: agent).coroutine(
            description="梳理案件事实",
            task="整理案件",
            runtime=runtime(context={"run_id": "run-1"}),
        )
    )

    assert observed == [
        ({"intent": "legal_question"}, {"run_id": "run-1"})
    ]
    assert json.loads(result)["result"] == {
        "assessment": {"intent": "legal_question"},
        "response_contract": {"answer_first": True},
    }


def test_delegation_tool_enforces_timeout() -> None:
    class SlowAgent:
        async def ainvoke(self, graph_input, *, config=None, context=None):
            del graph_input, config, context
            await asyncio.sleep(0.05)
            return {"messages": [AIMessage(content="late")]}

    spec = AgentDefinition(
        name="researcher",
        description="Research one bounded question.",
        system_prompt="Return sourced findings.",
        timeout_seconds=0.001,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(
            create_subagent_tool(spec, lambda _definition: SlowAgent()).coroutine(
                description="研究法规依据",
                task="研究法规",
                runtime=runtime(),
            )
        )


def test_delegation_tool_uses_host_owned_input_builder() -> None:
    agent = StubAgent({"messages": [AIMessage(content="完成")]})
    observed = []

    def build_input(task, tool_runtime):
        observed.append((task, tool_runtime.context))
        return f"{task}\n<context>{tool_runtime.context['case_data']}</context>"

    spec = AgentDefinition(
        name="case_analyst",
        description="Frame one legal case.",
        system_prompt="Analyze grounded facts.",
        input_builder=build_input,
    )

    asyncio.run(
        create_subagent_tool(spec, lambda _definition: agent).coroutine(
            description="梳理案件事实",
            task="提取事实和问题",
            runtime=runtime(context={"case_data": "用户原话"}),
        )
    )

    assert observed == [("提取事实和问题", {"case_data": "用户原话"})]
    assert agent.calls[0]["graph_input"]["messages"][0].content == (
        "提取事实和问题\n<context>用户原话</context>"
    )
