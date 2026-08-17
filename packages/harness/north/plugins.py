from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from langchain.agents.middleware import AgentMiddleware

from .config import AppConfig
from .subagents import AgentDefinition

PluginScope = Literal["application", "lead_agent", "subagent"]


class RegistrationHandle:
    """Reversible registration owned by one installed plugin."""

    def __init__(self, dispose: Callable[[], None]) -> None:
        self._dispose_callback = dispose
        self._disposed = False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._dispose_callback()


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Host-owned context exposed while one plugin is installed."""

    config: AppConfig
    scope: PluginScope
    plugin_id: str
    model: Any
    system_prompt: str
    tools: list[Any]
    middlewares: list[AgentMiddleware]
    agent_definitions: list[AgentDefinition]
    _handles: list[RegistrationHandle]

    def register_tool(self, tool: Any) -> RegistrationHandle:
        self.tools.append(tool)

        def dispose() -> None:
            if tool in self.tools:
                self.tools.remove(tool)

        handle = RegistrationHandle(dispose)
        self._handles.append(handle)
        return handle

    def register_middleware(self, middleware: AgentMiddleware) -> RegistrationHandle:
        self.middlewares.append(middleware)

        def dispose() -> None:
            if middleware in self.middlewares:
                self.middlewares.remove(middleware)

        handle = RegistrationHandle(dispose)
        self._handles.append(handle)
        return handle

    def register_agent_definition(self, definition: AgentDefinition) -> RegistrationHandle:
        if any(item.name == definition.name for item in self.agent_definitions):
            raise ValueError(f"Duplicate agent definition name: {definition.name}")
        self.agent_definitions.append(definition)

        def dispose() -> None:
            if definition in self.agent_definitions:
                self.agent_definitions.remove(definition)

        handle = RegistrationHandle(dispose)
        self._handles.append(handle)
        return handle


class AgentPlugin(Protocol):
    """Plugin contract for host-owned Agent composition."""

    plugin_id: str
    requires: tuple[str, ...]
    scopes: tuple[PluginScope, ...]

    def install(self, context: PluginContext) -> RegistrationHandle | None:
        ...


@dataclass(frozen=True, slots=True)
class FunctionPlugin:
    """Small typed plugin for an in-process host composition root."""

    plugin_id: str
    installer: Callable[[PluginContext], RegistrationHandle | None]
    requires: tuple[str, ...] = ()
    scopes: tuple[PluginScope, ...] = ("lead_agent",)

    def install(self, context: PluginContext) -> RegistrationHandle | None:
        return self.installer(context)


@dataclass(slots=True)
class PluginInstallation:
    context: PluginContext
    handles: list[RegistrationHandle]

    def dispose(self) -> None:
        for handle in reversed(self.handles):
            handle.dispose()


def install_plugins(
    plugins: Sequence[AgentPlugin],
    *,
    config: AppConfig,
    scope: PluginScope,
    model: Any,
    system_prompt: str,
    tools: list[Any],
) -> PluginInstallation:
    """Install a dependency-ordered plugin set for one Agent scope."""

    by_id: dict[str, AgentPlugin] = {}
    for plugin in plugins:
        if plugin.plugin_id in by_id:
            raise ValueError(f"Duplicate plugin id: {plugin.plugin_id}")
        by_id[plugin.plugin_id] = plugin

    ordered: list[AgentPlugin] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(plugin: AgentPlugin) -> None:
        if plugin.plugin_id in visited:
            return
        if plugin.plugin_id in visiting:
            raise ValueError(f"Plugin dependency cycle at: {plugin.plugin_id}")
        visiting.add(plugin.plugin_id)
        for dependency in plugin.requires:
            dependency_plugin = by_id.get(dependency)
            if dependency_plugin is None:
                raise ValueError(
                    f"Plugin {plugin.plugin_id} requires missing plugin: {dependency}"
                )
            visit(dependency_plugin)
        visiting.remove(plugin.plugin_id)
        visited.add(plugin.plugin_id)
        ordered.append(plugin)

    for plugin in plugins:
        visit(plugin)

    middlewares: list[AgentMiddleware] = []
    definitions: list[AgentDefinition] = []
    handles: list[RegistrationHandle] = []
    context = PluginContext(
        config=config,
        scope=scope,
        plugin_id="",
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        middlewares=middlewares,
        agent_definitions=definitions,
        _handles=handles,
    )
    installed_ids: set[str] = set()
    try:
        for plugin in ordered:
            if scope not in plugin.scopes:
                continue
            if any(dependency not in installed_ids for dependency in plugin.requires):
                raise ValueError(
                    f"Plugin {plugin.plugin_id} has a dependency outside scope {scope}: "
                    + ", ".join(plugin.requires)
                )
            scoped_context = PluginContext(
                config=context.config,
                scope=context.scope,
                plugin_id=plugin.plugin_id,
                model=context.model,
                system_prompt=context.system_prompt,
                tools=context.tools,
                middlewares=context.middlewares,
                agent_definitions=context.agent_definitions,
                _handles=context._handles,
            )
            handle = plugin.install(scoped_context)
            if handle is not None and handle not in handles:
                handles.append(handle)
            installed_ids.add(plugin.plugin_id)
    except BaseException:
        PluginInstallation(context, handles).dispose()
        raise

    return PluginInstallation(context, handles)


__all__ = [
    "AgentPlugin",
    "FunctionPlugin",
    "PluginContext",
    "PluginInstallation",
    "PluginScope",
    "RegistrationHandle",
    "install_plugins",
]
