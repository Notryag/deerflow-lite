import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from north.agents.middlewares import (
    ClarificationMiddleware,
    LoopDetectionMiddleware,
    TitleMiddleware,
    ToolErrorHandlingMiddleware,
    get_default_middlewares,
)


class _TitleModel:
    def __init__(self, content: str = "劳动合同解除补偿") -> None:
        self.content = content
        self.calls = 0

    async def ainvoke(self, prompt, config=None):
        del prompt, config
        self.calls += 1
        return AIMessage(content=self.content)


def test_default_middlewares_are_registered():
    middlewares = get_default_middlewares()

    assert [middleware.name for middleware in middlewares] == [
        "ToolErrorHandlingMiddleware",
        "LoopDetectionMiddleware",
        "ClarificationMiddleware",
    ]


def test_title_middleware_generates_once_after_first_exchange():
    model = _TitleModel()
    middleware = TitleMiddleware(model=model, max_chars=20)
    state = {
        "messages": [
            HumanMessage(content="公司辞退我，应该怎么索要赔偿？"),
            AIMessage(content="需要先区分合法解除和违法解除。"),
        ]
    }

    result = asyncio.run(middleware.aafter_model(state, SimpleNamespace()))

    assert result == {"title": "劳动合同解除补偿"}
    assert model.calls == 1


def test_title_middleware_does_not_overwrite_existing_title():
    model = _TitleModel()
    middleware = TitleMiddleware(model=model)
    state = {
        "title": "用户命名的案件",
        "messages": [
            HumanMessage(content="公司辞退我"),
            AIMessage(content="请补充解除理由。"),
        ],
    }

    result = asyncio.run(middleware.aafter_model(state, SimpleNamespace()))

    assert result is None
    assert model.calls == 0


def test_title_middleware_falls_back_to_first_user_message():
    middleware = TitleMiddleware(model=None, max_chars=12)
    state = {
        "messages": [
            HumanMessage(content="公司没有提前通知就把我辞退了"),
            AIMessage(content="可以先核对解除通知。"),
        ]
    }

    result = asyncio.run(middleware.aafter_model(state, SimpleNamespace()))

    assert result == {"title": "公司没有提前通知就..."}


def test_tool_error_middleware_converts_exceptions_to_tool_message():
    middleware = ToolErrorHandlingMiddleware()
    request = SimpleNamespace(tool_call={"id": "tool-1", "name": "web_fetch", "args": {"url": "https://example.com"}})

    result = middleware.wrap_tool_call(request, lambda _: (_ for _ in ()).throw(RuntimeError("network down")))

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.tool_call_id == "tool-1"
    assert "web_fetch" in result.content
    assert "network down" in result.content


def test_tool_error_middleware_converts_async_exceptions_to_tool_message():
    middleware = ToolErrorHandlingMiddleware()
    request = SimpleNamespace(tool_call={"id": "tool-1", "name": "web_fetch", "args": {}})

    async def fail(_):
        raise RuntimeError("network down")

    result = asyncio.run(middleware.awrap_tool_call(request, fail))

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "network down" in result.content


def test_loop_detection_middleware_blocks_repeated_identical_calls():
    middleware = LoopDetectionMiddleware(max_same_call_count=2)
    repeated_call = {"name": "web_search", "args": {"query": "deerflow"}}
    request = SimpleNamespace(
        tool_call={"id": "tool-3", **repeated_call},
        state={
            "messages": [
                HumanMessage(content="Research DeerFlow"),
                AIMessage(content="", tool_calls=[{"id": "tool-1", **repeated_call}]),
                ToolMessage(content="first", tool_call_id="tool-1"),
                AIMessage(content="", tool_calls=[{"id": "tool-2", **repeated_call}]),
                ToolMessage(content="second", tool_call_id="tool-2"),
                AIMessage(content="", tool_calls=[{"id": "tool-3", **repeated_call}]),
            ]
        },
    )

    result = middleware.wrap_tool_call(request, lambda _: (_ for _ in ()).throw(AssertionError("handler should not run")))

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "repeated tool loop" in result.content


def test_loop_detection_middleware_allows_async_tool_call():
    middleware = LoopDetectionMiddleware()
    request = SimpleNamespace(
        tool_call={"id": "tool-1", "name": "web_search", "args": {"query": "deerflow"}},
        state={"messages": []},
    )

    async def handle(_):
        return ToolMessage(content="ok", tool_call_id="tool-1")

    result = asyncio.run(middleware.awrap_tool_call(request, handle))

    assert result.content == "ok"


def test_clarification_middleware_marks_pending_question():
    middleware = ClarificationMiddleware()
    request = SimpleNamespace(
        tool_call={"id": "tool-1", "name": "ask_clarification", "args": {"question": "Which company?"}},
        state={"thread_data": {"source": "user"}},
    )

    result = middleware.wrap_tool_call(
        request,
        lambda _: ToolMessage(
            content="Clarification needed: Which company?",
            tool_call_id="tool-1",
            name="ask_clarification",
        ),
    )

    assert isinstance(result, Command)
    assert result.update["clarification_request"] == {
        "question": "Which company?",
        "response_kind": "free_text",
        "options": [],
    }
    assert len(result.update["messages"]) == 1


def test_clarification_middleware_marks_pending_question_async():
    middleware = ClarificationMiddleware()
    request = SimpleNamespace(
        tool_call={"id": "tool-1", "name": "ask_clarification", "args": {"question": "When?"}},
        state={},
    )

    async def handle(_):
        return ToolMessage(content="Clarification needed: When?", tool_call_id="tool-1")

    result = asyncio.run(middleware.awrap_tool_call(request, handle))

    assert isinstance(result, Command)
    assert result.update["clarification_request"]["question"] == "When?"


def test_clarification_middleware_preserves_structured_choices():
    middleware = ClarificationMiddleware()
    request = SimpleNamespace(
        tool_call={
            "id": "tool-1",
            "name": "ask_clarification",
            "args": {
                "question": "When should it start?",
                "response_kind": "single_choice",
                "options": ["Tomorrow 09:00", "Tomorrow 14:00"],
            },
        },
        state={},
    )

    result = middleware.wrap_tool_call(
        request,
        lambda _: ToolMessage(content="Choose a time", tool_call_id="tool-1"),
    )

    assert result.update["clarification_request"] == {
        "question": "When should it start?",
        "response_kind": "single_choice",
        "options": ["Tomorrow 09:00", "Tomorrow 14:00"],
    }


def test_clarification_middleware_downgrades_empty_choices_to_free_text():
    middleware = ClarificationMiddleware()
    request = SimpleNamespace(
        tool_call={
            "id": "tool-1",
            "name": "ask_clarification",
            "args": {
                "question": "  When should it start?  ",
                "response_kind": "single_choice",
                "options": ["  "],
            },
        },
        state={},
    )

    result = middleware.wrap_tool_call(
        request,
        lambda _: ToolMessage(content="Choose a time", tool_call_id="tool-1"),
    )

    assert result.update["clarification_request"] == {
        "question": "When should it start?",
        "response_kind": "free_text",
        "options": [],
    }


def test_clarification_middleware_clears_pending_question_on_user_reply():
    middleware = ClarificationMiddleware()

    update = middleware.before_model(
        {
            "clarification_request": {"question": "Which company?"},
            "messages": [HumanMessage(content="OpenAI")],
        },
        runtime=None,
    )

    assert update == {"clarification_request": None}
