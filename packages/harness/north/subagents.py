from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

_SUBAGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class SubagentSpec:
    """Host-owned declaration for one bounded, stateless specialist agent."""

    name: str
    description: str
    system_prompt: str
    tools: tuple[Any, ...] = ()
    skills: tuple[str, ...] = ()
    result_schema: Any | None = None
    timeout_seconds: float = 90.0
    recursion_limit: int = 20

    def __post_init__(self) -> None:
        name = self.name.strip()
        description = self.description.strip()
        system_prompt = self.system_prompt.strip()
        if not _SUBAGENT_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "subagent name must start with a lowercase letter and contain only "
                "lowercase letters, digits, and underscores"
            )
        if not description:
            raise ValueError("subagent description cannot be blank")
        if not system_prompt:
            raise ValueError("subagent system_prompt cannot be blank")
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise ValueError("subagent timeout_seconds must be positive")
        if isinstance(self.recursion_limit, bool) or self.recursion_limit < 2:
            raise ValueError("subagent recursion_limit must be at least 2")

        normalized_skills: list[str] = []
        for raw_name in self.skills:
            skill_name = raw_name.strip()
            if skill_name and skill_name not in normalized_skills:
                normalized_skills.append(skill_name)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "system_prompt", system_prompt)
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "skills", tuple(normalized_skills))

    @property
    def tool_name(self) -> str:
        return f"delegate_{self.name}"


def create_subagent_tool(spec: SubagentSpec, agent: Any) -> StructuredTool:
    """Expose one compiled subagent as a bounded delegation tool."""

    async def delegate(task: str, *, runtime: ToolRuntime[dict[str, Any]]) -> str:
        normalized_task = task.strip()
        if not normalized_task:
            raise ValueError("subagent task cannot be blank")
        ainvoke = getattr(agent, "ainvoke", None)
        if not callable(ainvoke):
            raise TypeError("Subagent does not expose ainvoke")

        config = _subagent_config(runtime.config, spec)
        async with asyncio.timeout(spec.timeout_seconds):
            result = await ainvoke(
                {"messages": [HumanMessage(content=normalized_task)]},
                config=config,
                context=runtime.context,
            )
        return _render_subagent_result(spec, result)

    return StructuredTool.from_function(
        coroutine=delegate,
        name=spec.tool_name,
        description=(
            f"Delegate one bounded task to the {spec.name} specialist. "
            f"{spec.description} Return its result to the lead agent for synthesis."
        ),
    )


def _subagent_config(config: Mapping[str, Any] | None, spec: SubagentSpec) -> dict[str, Any]:
    resolved = dict(config or {})
    tags = [
        str(tag)
        for tag in resolved.get("tags", [])
        if str(tag) != "lead_agent" and not str(tag).startswith("subagent:")
    ]
    tags.append(f"subagent:{spec.name}")
    resolved["tags"] = tags
    resolved["recursion_limit"] = spec.recursion_limit

    configurable = dict(resolved.get("configurable") or {})
    configurable.pop("checkpoint_id", None)
    if configurable:
        resolved["configurable"] = configurable
    else:
        resolved.pop("configurable", None)
    return resolved


def _render_subagent_result(spec: SubagentSpec, result: Any) -> str:
    if not isinstance(result, Mapping):
        raise TypeError("Subagent result must be a graph-state mapping")

    if spec.result_schema is not None:
        structured = result.get("structured_response")
        if structured is None:
            raise RuntimeError("Subagent completed without a structured response")
        payload = _serialize_value(structured)
    else:
        payload = _final_assistant_text(result.get("messages"))
        if not payload:
            raise RuntimeError("Subagent completed without a final assistant response")

    return json.dumps(
        {"subagent": spec.name, "result": payload},
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
