from __future__ import annotations

import pytest
from north.config import AppConfig
from north.plugins import FunctionPlugin, install_plugins


def _install(plugins, *, scope="lead_agent"):
    return install_plugins(
        plugins,
        config=AppConfig(model_name="openai:gpt-test"),
        scope=scope,
        model=object(),
        system_prompt="Test prompt.",
        tools=[],
    )


def test_plugins_install_in_dependency_order() -> None:
    installed = []
    first = FunctionPlugin(
        plugin_id="first",
        installer=lambda context: installed.append(context.plugin_id),
    )
    second = FunctionPlugin(
        plugin_id="second",
        installer=lambda context: installed.append(context.plugin_id),
        requires=("first",),
    )

    _install([second, first])

    assert installed == ["first", "second"]


def test_plugin_registration_is_reversible() -> None:
    tool = object()
    plugin = FunctionPlugin(
        plugin_id="tools",
        installer=lambda context: context.register_tool(tool),
    )

    installation = _install([plugin])

    assert installation.context.tools == [tool]
    installation.dispose()
    assert installation.context.tools == []


def test_plugin_registry_rejects_duplicate_ids() -> None:
    plugin = FunctionPlugin(plugin_id="duplicate", installer=lambda context: None)

    with pytest.raises(ValueError, match="Duplicate plugin id"):
        _install([plugin, plugin])


def test_plugin_registry_rejects_missing_dependencies() -> None:
    plugin = FunctionPlugin(
        plugin_id="consumer",
        installer=lambda context: None,
        requires=("service",),
    )

    with pytest.raises(ValueError, match="requires missing plugin"):
        _install([plugin])


def test_plugin_registry_rejects_dependency_outside_scope() -> None:
    service = FunctionPlugin(
        plugin_id="service",
        installer=lambda context: None,
        scopes=("lead_agent",),
    )
    consumer = FunctionPlugin(
        plugin_id="consumer",
        installer=lambda context: None,
        requires=("service",),
        scopes=("subagent",),
    )

    with pytest.raises(ValueError, match="dependency outside scope"):
        _install([service, consumer], scope="subagent")
