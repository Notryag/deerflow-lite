from types import SimpleNamespace

import pytest
from north.agent import build_agent, create_chat_model
from north.config import AppConfig
from north.subagents import SubagentSpec


def test_create_chat_model_defaults_plain_names_to_openai_provider(monkeypatch):
    captured = {}

    def fake_init_chat_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("north.agent.init_chat_model", fake_init_chat_model)

    create_chat_model("qwen3.6-plus")

    assert captured == {"model": "qwen3.6-plus", "model_provider": "openai"}


def test_create_chat_model_preserves_explicit_provider(monkeypatch):
    captured = {}

    def fake_init_chat_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("north.agent.init_chat_model", fake_init_chat_model)

    create_chat_model("openai:gpt-4o-mini")

    assert captured == {"model": "gpt-4o-mini", "model_provider": "openai"}


def test_create_chat_model_forwards_host_headers(monkeypatch):
    captured = {}

    def fake_init_chat_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("north.agent.init_chat_model", fake_init_chat_model)

    create_chat_model(
        "openai:gpt-4o-mini",
        default_headers={"Northgate-Metadata": '{"run_id":"run-1"}'},
    )

    assert captured == {
        "model": "gpt-4o-mini",
        "model_provider": "openai",
        "default_headers": {"Northgate-Metadata": '{"run_id":"run-1"}'},
    }


def test_create_chat_model_forwards_host_connection_options(monkeypatch):
    captured = {}

    def fake_init_chat_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("north.agent.init_chat_model", fake_init_chat_model)

    create_chat_model(
        "openai:gpt-4o-mini",
        model_options={"base_url": "http://northgate:8080/v1", "api_key": "application-key"},
    )

    assert captured == {
        "model": "gpt-4o-mini",
        "model_provider": "openai",
        "base_url": "http://northgate:8080/v1",
        "api_key": "application-key",
    }


def test_create_chat_model_rejects_reserved_connection_options() -> None:
    with pytest.raises(ValueError, match="model_provider"):
        create_chat_model(
            "openai:gpt-4o-mini",
            model_options={"model_provider": "anthropic"},
        )


def test_build_agent_injects_skill_catalog_not_skill_body(monkeypatch, tmp_path):
    skill_dir = tmp_path / "skills" / "research"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: research\ndescription: Web research workflow\n---\nDetailed body content.\n",
        encoding="utf-8",
    )

    captured = {}

    class StubModel:
        pass

    def fake_create_chat_model(name, thinking_enabled=False):
        _ = name, thinking_enabled
        return StubModel()

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("north.agent.create_chat_model", fake_create_chat_model)
    monkeypatch.setattr("north.agent._supports_tool_binding", lambda model: True)
    monkeypatch.setattr("north.agent.create_agent", fake_create_agent)

    build_agent(
        AppConfig(
            model_name="openai:gpt-4o-mini",
            system_prompt="Base prompt.",
            skills_dir=tmp_path / "skills",
        )
    )

    assert "<available_skills>" in captured["system_prompt"]
    assert "<location>skill://research/SKILL.md</location>" in captured["system_prompt"]
    assert "Detailed body content." not in captured["system_prompt"]


def test_build_agent_configures_run_aware_summarization(monkeypatch):
    captured = {}

    class StubModel:
        def with_config(self, **kwargs):
            captured["summary_model_config"] = kwargs
            return self

    class StubSummarizationMiddleware:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("north.agent.create_chat_model", lambda *args, **kwargs: StubModel())
    monkeypatch.setattr("north.agent._supports_tool_binding", lambda model: True)
    monkeypatch.setattr("north.agent.NorthSummarizationMiddleware", StubSummarizationMiddleware)
    monkeypatch.setattr("north.agent.create_agent", lambda **kwargs: object())

    build_agent(
        AppConfig(
            model_name="openai:gpt-test",
            summarization_enabled=True,
            summarization_normal_trigger_tokens=6000,
            summarization_emergency_trigger_tokens=12000,
            summarization_message_ceiling=60,
            summarization_target_tokens=2000,
            summarization_min_growth_tokens=3000,
            summarization_max_emergency_compactions=2,
        ),
        tools=[],
    )

    assert captured["normal_trigger_tokens"] == 6000
    assert captured["emergency_trigger_tokens"] == 12000
    assert captured["message_ceiling"] == 60
    assert captured["target_tokens"] == 2000
    assert captured["min_growth_tokens"] == 3000
    assert captured["max_emergency_compactions"] == 2
    assert captured["context_token_overhead"] > 0
    assert captured["summary_model_config"] == {"tags": ["middleware:summarization"]}


def test_build_agent_appends_host_middlewares_after_runtime_defaults(monkeypatch):
    captured = {}
    runtime_middleware = object()
    host_middleware = object()

    class StubModel:
        pass

    monkeypatch.setattr("north.agent.create_chat_model", lambda *args, **kwargs: StubModel())
    monkeypatch.setattr("north.agent._supports_tool_binding", lambda model: True)
    monkeypatch.setattr(
        "north.agent.resolve_middlewares", lambda config: [runtime_middleware]
    )
    monkeypatch.setattr(
        "north.agent.create_agent", lambda **kwargs: captured.update(kwargs) or object()
    )

    build_agent(
        AppConfig(model_name="openai:gpt-test"),
        tools=[],
        additional_middlewares=[host_middleware],
    )

    assert captured["middleware"] == [runtime_middleware, host_middleware]


def test_build_agent_isolates_subagent_tools_and_checkpointer(monkeypatch):
    calls = []
    model_tags = []
    parent_checkpointer = object()
    lead_tool = SimpleNamespace(name="lead_tool")
    specialist_tool = SimpleNamespace(name="specialist_tool")

    class StubModel:
        def with_config(self, **kwargs):
            model_tags.append(kwargs["tags"])
            return self

    monkeypatch.setattr("north.agent.create_chat_model", lambda *args, **kwargs: StubModel())
    monkeypatch.setattr("north.agent._supports_tool_binding", lambda model: True)
    monkeypatch.setattr(
        "north.agent.create_agent",
        lambda **kwargs: calls.append(kwargs) or object(),
    )

    build_agent(
        AppConfig(model_name="openai:gpt-test", system_prompt="Lead prompt."),
        tools=[lead_tool],
        checkpointer=parent_checkpointer,
        subagents=[
            SubagentSpec(
                name="case_analyst",
                description="Frame one legal case.",
                system_prompt="Specialist prompt.",
                tools=(specialist_tool,),
                result_schema=dict,
                recursion_limit=10,
            )
        ],
    )

    child_call, lead_call = calls
    assert child_call["system_prompt"] == "Specialist prompt."
    assert child_call["tools"] == [specialist_tool]
    assert child_call["checkpointer"] is None
    assert child_call["response_format"] is dict
    assert [tool.name for tool in lead_call["tools"]] == [
        "lead_tool",
        "delegate_case_analyst",
    ]
    assert lead_call["checkpointer"] is parent_checkpointer
    assert lead_call["response_format"] is None
    assert child_call["context_schema"] is dict
    assert lead_call["context_schema"] is dict
    assert model_tags == [["lead_agent"], ["subagent:case_analyst"]]


def test_build_agent_rejects_delegation_tool_collision(monkeypatch):
    class StubModel:
        pass

    monkeypatch.setattr("north.agent.create_chat_model", lambda *args, **kwargs: StubModel())
    monkeypatch.setattr("north.agent._supports_tool_binding", lambda model: True)

    with pytest.raises(ValueError, match="Duplicate delegation tool name"):
        build_agent(
            AppConfig(model_name="openai:gpt-test"),
            tools=[SimpleNamespace(name="delegate_case_analyst")],
            subagents=[
                SubagentSpec(
                    name="case_analyst",
                    description="Frame one legal case.",
                    system_prompt="Specialist prompt.",
                )
            ],
        )
