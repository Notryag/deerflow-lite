from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

_AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
AgentResultProcessor = Callable[[Any, ToolRuntime[dict[str, Any]]], Any | Awaitable[Any]]
AgentInputBuilder = Callable[
    [str, ToolRuntime[dict[str, Any]]], str | Awaitable[str]
]
AgentBuilder = Callable[["AgentDefinition"], Any]


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Host-owned declaration for one bounded specialist Agent role."""

    name: str
    description: str
    system_prompt: str
    display_name: str | None = None
    tools: tuple[Any, ...] = ()
    skills: tuple[str, ...] = ()
    result_schema: Any | None = None
    result_processor: AgentResultProcessor | None = None
    input_builder: AgentInputBuilder | None = None
    timeout_seconds: float = 90.0
    recursion_limit: int = 20

    def __post_init__(self) -> None:
        name = self.name.strip()
        description = self.description.strip()
        system_prompt = self.system_prompt.strip()
        display_name = (self.display_name or name).strip()
        if not _AGENT_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "agent definition name must start with a lowercase letter and contain "
                "only lowercase letters, digits, and underscores"
            )
        if not description:
            raise ValueError("agent definition description cannot be blank")
        if not system_prompt:
            raise ValueError("agent definition system_prompt cannot be blank")
        if not display_name:
            raise ValueError("agent definition display_name cannot be blank")
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise ValueError("agent definition timeout_seconds must be positive")
        if isinstance(self.recursion_limit, bool) or self.recursion_limit < 2:
            raise ValueError("agent definition recursion_limit must be at least 2")

        normalized_skills: list[str] = []
        for raw_name in self.skills:
            skill_name = raw_name.strip()
            if skill_name and skill_name not in normalized_skills:
                normalized_skills.append(skill_name)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "system_prompt", system_prompt)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "skills", tuple(normalized_skills))

    @property
    def tool_name(self) -> str:
        return f"delegate_{self.name}"


def create_subagent_tool(
    definition: AgentDefinition,
    build_child_agent: AgentBuilder,
) -> StructuredTool:
    """Expose one lazily-created Agent Definition as a bounded delegation tool."""

    async def delegate(
        description: str,
        task: str,
        *,
        runtime: ToolRuntime[dict[str, Any]],
    ) -> str:
        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("subagent description cannot be blank")
        normalized_task = task.strip()
        if not normalized_task:
            raise ValueError("subagent task cannot be blank")
        child_input = normalized_task
        if definition.input_builder is not None:
            built = definition.input_builder(normalized_task, runtime)
            child_input = await built if inspect.isawaitable(built) else built
            if not isinstance(child_input, str) or not child_input.strip():
                raise ValueError("agent definition input_builder must return non-blank text")
            child_input = child_input.strip()

        agent = build_child_agent(definition)
        ainvoke = getattr(agent, "ainvoke", None)
        if not callable(ainvoke):
            raise TypeError("Subagent does not expose ainvoke")

        config = _agent_config(runtime.config, definition)
        async with asyncio.timeout(definition.timeout_seconds):
            result = await ainvoke(
                {"messages": [HumanMessage(content=child_input)]},
                config=config,
                context=runtime.context,
            )
        payload = _agent_result_payload(definition, result)
        if definition.result_processor is not None:
            processed = definition.result_processor(payload, runtime)
            payload = await processed if inspect.isawaitable(processed) else processed
        return _render_agent_result(definition, payload)

    return StructuredTool.from_function(
        coroutine=delegate,
        name=definition.tool_name,
        description=(
            f"Delegate one bounded task to the {definition.name} specialist. "
            f"{definition.description} Give description a short user-facing activity label, then give "
            "task only the specialist's objective and boundaries. Return its result to the lead "
            "agent for synthesis."
        ),
        metadata={
            "subagent_type": definition.name,
            "display_name": definition.display_name,
        },
    )


def _agent_config(
    config: Mapping[str, Any] | None,
    definition: AgentDefinition,
) -> dict[str, Any]:
    resolved = dict(config or {})
    tags = [
        str(tag)
        for tag in resolved.get("tags", [])
        if str(tag) != "lead_agent" and not str(tag).startswith("subagent:")
    ]
    tags.append(f"subagent:{definition.name}")
    resolved["tags"] = tags
    resolved["recursion_limit"] = definition.recursion_limit

    configurable = dict(resolved.get("configurable") or {})
    configurable.pop("checkpoint_id", None)
    if configurable:
        resolved["configurable"] = configurable
    else:
        resolved.pop("configurable", None)
    return resolved


def _agent_result_payload(definition: AgentDefinition, result: Any) -> Any:
    if not isinstance(result, Mapping):
        raise TypeError("Subagent result must be a graph-state mapping")

    if definition.result_schema is not None:
        structured = result.get("structured_response")
        if structured is None:
            raise RuntimeError("Subagent completed without a structured response")
        return structured
    payload = _final_assistant_text(result.get("messages"))
    if not payload:
        raise RuntimeError("Subagent completed without a final assistant response")
    return payload


def _render_agent_result(definition: AgentDefinition, payload: Any) -> str:
    return json.dumps(
        {"subagent": definition.name, "result": _serialize_value(payload)},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _final_assistant_text(messages: Any) -> str:
    if not isinstance(messages, (list, tuple)):
        return ""
    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue
        content = message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                str(block.get("text", "")).strip()
                for block in content
                if isinstance(block, Mapping) and block.get("type") == "text"
            ]
            return "\n".join(part for part in parts if part)
    return ""


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


__all__ = ["AgentDefinition", "create_subagent_tool"]
