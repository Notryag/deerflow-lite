from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.messages.utils import count_tokens_approximately

from .agents.middlewares import (
    CompactionHook,
    NorthSummarizationMiddleware,
    TitleMiddleware,
)
from .config import AppConfig
from .runtime import (
    get_checkpointer as resolve_checkpointer,
)
from .runtime import (
    get_middlewares as resolve_middlewares,
)
from .runtime import (
    get_skills as resolve_skills,
)
from .runtime import (
    get_state_schema,
)
from .runtime import (
    get_system_prompt as resolve_system_prompt,
)
from .runtime import (
    get_tools as resolve_tools,
)
from .subagents import SubagentSpec, create_subagent_tool


def _supports_tool_binding(model) -> bool:
    bind_tools = getattr(type(model), "bind_tools", None)
    return bind_tools is not None and bind_tools is not BaseChatModel.bind_tools


def create_chat_model(
    name: str,
    thinking_enabled: bool = False,
    default_headers: dict[str, str] | None = None,
    model_options: dict[str, object] | None = None,
):
    """Create a chat model from a provider-prefixed or plain model name."""
    provider, separator, model_name = name.partition(":")
    if separator:
        kwargs = {"model": model_name, "model_provider": provider}
    else:
        # Treat bare model names as OpenAI-compatible by default so providers
        # behind OPENAI_BASE_URL (DashScope, OpenRouter-compatible gateways, etc.)
        # work without forcing a prefix in APP_MODEL_NAME.
        kwargs = {"model": name, "model_provider": "openai"}
    if default_headers:
        kwargs["default_headers"] = dict(default_headers)
    if model_options:
        reserved = {"model", "model_provider", "default_headers"} & model_options.keys()
        if reserved:
            raise ValueError(f"Model options cannot override: {', '.join(sorted(reserved))}")
        kwargs.update(model_options)

    # The flag stays in the public config surface even though the minimal app
    # does not apply provider-specific reasoning parameters yet.
    _ = thinking_enabled
    return init_chat_model(**kwargs)


def build_agent(
    config: AppConfig,
    *,
    tools: list | None = None,
    middlewares=None,
    additional_middlewares=None,
    checkpointer=None,
    skills: Sequence[str] | None = None,
    compaction_hooks: list[CompactionHook] | None = None,
    subagents: Sequence[SubagentSpec] | None = None,
    response_format: Any | None = None,
):
    resolved_checkpointer = (
        checkpointer if checkpointer is not None else resolve_checkpointer(config)
    )
    return _build_agent(
        config,
        tools=tools,
        middlewares=middlewares,
        additional_middlewares=additional_middlewares,
        checkpointer=resolved_checkpointer,
        skills=skills,
        compaction_hooks=compaction_hooks,
        subagents=subagents,
        response_format=response_format,
        caller_tag="lead_agent",
    )


def _build_agent(
    config: AppConfig,
    *,
    tools: list | None,
    middlewares,
    additional_middlewares,
    checkpointer,
    skills: Sequence[str] | None,
    compaction_hooks: list[CompactionHook] | None,
    subagents: Sequence[SubagentSpec] | None,
    response_format: Any | None,
    caller_tag: str,
):
    model_kwargs = {
        "name": config.model_name,
        "thinking_enabled": config.thinking_enabled,
    }
    if config.model_headers:
        model_kwargs["default_headers"] = config.model_headers
    if config.model_options:
        model_kwargs["model_options"] = config.model_options
    model = create_chat_model(**model_kwargs)
    supports_tool_binding = _supports_tool_binding(model)
    with_config = getattr(model, "with_config", None)
    if callable(with_config):
        model = with_config(tags=[caller_tag])
    resolved_skills = resolve_skills(config, skill_names=skills)
    resolved_tools = (
        list(tools) if tools is not None else list(resolve_tools(config, skills=resolved_skills))
    )
    if subagents:
        existing_tool_names = {_tool_name(tool) for tool in resolved_tools}
        delegation_names: set[str] = set()
        for spec in subagents:
            if spec.tool_name in existing_tool_names or spec.tool_name in delegation_names:
                raise ValueError(f"Duplicate delegation tool name: {spec.tool_name}")
            delegation_names.add(spec.tool_name)
            child_config = replace(
                config,
                system_prompt=spec.system_prompt,
                skills_dir=(config.skills_dir if spec.skills else None),
                enabled_skills=spec.skills,
                recursion_limit=spec.recursion_limit,
                auto_title_enabled=False,
            )
            child_agent = _build_agent(
                child_config,
                tools=list(spec.tools),
                middlewares=None,
                additional_middlewares=None,
                checkpointer=None,
                skills=(spec.skills if spec.skills else None),
                compaction_hooks=None,
                subagents=None,
                response_format=spec.result_schema,
                caller_tag=f"subagent:{spec.name}",
            )
            resolved_tools.append(create_subagent_tool(spec, child_agent))
    if not supports_tool_binding:
        resolved_tools = []
    system_prompt = resolve_system_prompt(config, skills=resolved_skills)

    resolved_middlewares = list(
        middlewares if middlewares is not None else resolve_middlewares(config)
    )
    if additional_middlewares is not None:
        resolved_middlewares.extend(additional_middlewares)
    if config.auto_title_enabled:
        title_model_name = config.title_model_name or config.model_name
        title_model = create_chat_model(
            title_model_name,
            **({"default_headers": config.model_headers} if config.model_headers else {}),
            **({"model_options": config.model_options} if config.model_options else {}),
        )
        resolved_middlewares.append(
            TitleMiddleware(
                model=title_model,
                max_chars=config.title_max_chars,
            )
        )
    if config.summarization_enabled:
        summary_model = (
            create_chat_model(
                config.summarization_model_name,
                **({"default_headers": config.model_headers} if config.model_headers else {}),
                **({"model_options": config.model_options} if config.model_options else {}),
            )
            if config.summarization_model_name
            else model
        )
        summary_model = summary_model.with_config(tags=["middleware:summarization"])
        summarization_kwargs = {
            "model": summary_model,
            "normal_trigger_tokens": config.summarization_normal_trigger_tokens,
            "emergency_trigger_tokens": config.summarization_emergency_trigger_tokens,
            "message_ceiling": config.summarization_message_ceiling,
            "target_tokens": config.summarization_target_tokens,
            "min_growth_tokens": config.summarization_min_growth_tokens,
            "max_emergency_compactions": (
                config.summarization_max_emergency_compactions
            ),
            "context_token_overhead": count_tokens_approximately(
                [SystemMessage(content=system_prompt)],
                tools=resolved_tools,
            ),
            "compaction_hooks": compaction_hooks,
        }
        if config.summarization_summary_prompt is not None:
            summarization_kwargs["summary_prompt"] = config.summarization_summary_prompt
        resolved_middlewares.insert(0, NorthSummarizationMiddleware(**summarization_kwargs))

    return create_agent(
        model=model,
        tools=resolved_tools,
        middleware=resolved_middlewares,
        system_prompt=system_prompt,
        state_schema=get_state_schema(),
        context_schema=dict,
        checkpointer=checkpointer,
        response_format=response_format,
    )


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    return str(name) if name is not None else ""
