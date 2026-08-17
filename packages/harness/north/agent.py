from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.messages.utils import count_tokens_approximately

from .agents.middlewares import (
    CompactionHook,
    NorthSummarizationMiddleware,
    get_default_middlewares,
)
from .config import AppConfig
from .plugins import AgentPlugin, PluginContext, PluginScope, RegistrationHandle, install_plugins
from .runtime import get_checkpointer as resolve_checkpointer
from .runtime import get_skills as resolve_skills
from .runtime import get_state_schema
from .runtime import get_system_prompt as resolve_system_prompt
from .subagents import create_subagent_tool
from .tools import get_builtin_tools


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
        kwargs = {"model": name, "model_provider": "openai"}
    if default_headers:
        kwargs["default_headers"] = dict(default_headers)
    if model_options:
        reserved = {"model", "model_provider", "default_headers"} & model_options.keys()
        if reserved:
            raise ValueError(f"Model options cannot override: {', '.join(sorted(reserved))}")
        kwargs.update(model_options)

    _ = thinking_enabled
    return init_chat_model(**kwargs)


@dataclass(frozen=True, slots=True)
class _NorthRuntimePlugin:
    plugin_id: str = "north.runtime"
    requires: tuple[str, ...] = ()
    scopes: tuple[PluginScope, ...] = ("lead_agent", "subagent")

    def install(self, context: PluginContext) -> RegistrationHandle | None:
        handles: list[RegistrationHandle] = []
        for tool in get_builtin_tools():
            handles.append(context.register_tool(tool))
        for middleware in get_default_middlewares():
            handles.append(context.register_middleware(middleware))
        return RegistrationHandle(lambda: [handle.dispose() for handle in reversed(handles)])


@dataclass(frozen=True, slots=True)
class _NorthSummarizationPlugin:
    plugin_id: str
    config: AppConfig
    compaction_hooks: list[CompactionHook] | None
    requires: tuple[str, ...]
    scopes: tuple[PluginScope, ...] = ("lead_agent", "subagent")

    def install(self, context: PluginContext) -> RegistrationHandle | None:
        if not self.config.summarization_enabled:
            return None
        summary_model = (
            create_chat_model(
                self.config.summarization_model_name,
                **(
                    {"default_headers": self.config.model_headers}
                    if self.config.model_headers
                    else {}
                ),
                **(
                    {"model_options": self.config.model_options}
                    if self.config.model_options
                    else {}
                ),
            )
            if self.config.summarization_model_name
            else context.model
        )
        summary_model = summary_model.with_config(tags=["middleware:summarization"])
        middleware = NorthSummarizationMiddleware(
            model=summary_model,
            normal_trigger_tokens=self.config.summarization_normal_trigger_tokens,
            emergency_trigger_tokens=self.config.summarization_emergency_trigger_tokens,
            message_ceiling=self.config.summarization_message_ceiling,
            target_tokens=self.config.summarization_target_tokens,
            min_growth_tokens=self.config.summarization_min_growth_tokens,
            max_emergency_compactions=self.config.summarization_max_emergency_compactions,
            context_token_overhead=count_tokens_approximately(
                [SystemMessage(content=context.system_prompt)],
                tools=context.tools,
            ),
            compaction_hooks=self.compaction_hooks,
        )
        handle = context.register_middleware(middleware)
        context.middlewares.remove(middleware)
        context.middlewares.insert(0, middleware)
        return handle


def build_agent(
    config: AppConfig,
    *,
    plugins: Sequence[AgentPlugin] = (),
    checkpointer=None,
    skills: Sequence[str] | None = None,
    compaction_hooks: list[CompactionHook] | None = None,
):
    """Build a lead Agent from an explicit host plugin composition."""
    resolved_checkpointer = (
        checkpointer if checkpointer is not None else resolve_checkpointer(config)
    )
    return _build_agent(
        config,
        plugins=plugins,
        checkpointer=resolved_checkpointer,
        skills=skills,
        compaction_hooks=compaction_hooks,
        scope="lead_agent",
        caller_tag="lead_agent",
        response_format=None,
    )


def _build_agent(
    config: AppConfig,
    *,
    plugins: Sequence[AgentPlugin],
    checkpointer,
    skills: Sequence[str] | None,
    compaction_hooks: list[CompactionHook] | None,
    scope: PluginScope,
    caller_tag: str,
    response_format: Any | None,
    definition_tools: Sequence[Any] = (),
):
    model = create_chat_model(
        config.model_name,
        thinking_enabled=config.thinking_enabled,
        **({"default_headers": config.model_headers} if config.model_headers else {}),
        **({"model_options": config.model_options} if config.model_options else {}),
    )
    with_config = getattr(model, "with_config", None)
    if callable(with_config):
        model = with_config(tags=[caller_tag])

    resolved_skills = resolve_skills(config, skill_names=skills)
    system_prompt = resolve_system_prompt(config, skills=resolved_skills)
    initial_tools = list(definition_tools)
    runtime_plugin = _NorthRuntimePlugin()
    all_plugins: list[AgentPlugin] = [runtime_plugin, *plugins]
    if config.summarization_enabled:
        all_plugins.append(
            _NorthSummarizationPlugin(
                plugin_id="north.summarization",
                config=config,
                compaction_hooks=compaction_hooks,
                requires=(runtime_plugin.plugin_id,),
            )
        )
    installation = install_plugins(
        all_plugins,
        config=config,
        scope=scope,
        model=model,
        system_prompt=system_prompt,
        tools=initial_tools,
    )
    resolved_tools = installation.context.tools
    existing_tool_names = {_tool_name(tool) for tool in resolved_tools}
    for definition in installation.context.agent_definitions:
        if definition.tool_name in existing_tool_names:
            raise ValueError(f"Duplicate delegation tool name: {definition.tool_name}")
        existing_tool_names.add(definition.tool_name)
        child_config = replace(
            config,
            system_prompt=definition.system_prompt,
            skills_dir=(config.skills_dir if definition.skills else None),
            enabled_skills=definition.skills,
            recursion_limit=definition.recursion_limit,
        )
        child_agent = create_subagent_tool(
            definition,
            lambda child_definition, child_config=child_config: _build_agent(
                child_config,
                plugins=plugins,
                checkpointer=None,
                skills=child_definition.skills,
                compaction_hooks=None,
                scope="subagent",
                caller_tag=f"subagent:{child_definition.name}",
                definition_tools=child_definition.tools,
                response_format=child_definition.result_schema,
            ),
        )
        resolved_tools.append(child_agent)

    if not _supports_tool_binding(model):
        resolved_tools = []

    return create_agent(
        model=model,
        tools=resolved_tools,
        middleware=installation.context.middlewares,
        system_prompt=system_prompt,
        state_schema=get_state_schema(),
        context_schema=dict,
        checkpointer=checkpointer,
        response_format=response_format,
    )


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    return str(name) if name is not None else ""


__all__ = ["build_agent", "create_chat_model"]
