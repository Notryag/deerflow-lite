from __future__ import annotations

from collections.abc import Sequence

from ..checkpointer import get_default_checkpointer
from ..config import AppConfig
from ..skills import SkillSpec, compose_system_prompt, load_all_skills, load_skills
from ..state import ThreadState
from ..tools import get_builtin_tools
from .runs import DisconnectMode, RunConflictError, RunManager, RunRecord, RunStatus
from .invoke import RuntimeStreamEvent, invoke_agent_once
from .events import (
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeJournal,
    RuntimeUsageAccumulator,
    TokenUsage,
    normalize_token_usage,
)
from .service import RuntimeService
from .results import ClarificationRequest, RuntimeExecutionResult
from .stream_bridge import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    MemoryStreamBridge,
    REPLAY_GAP_EVENT,
    RedisStreamBridge,
    StreamBridge,
    StreamEvent,
)
from .worker import RunExecutor, RunLifecycleHooks


def get_skills(
    config: AppConfig,
    *,
    skill_names: Sequence[str] | None = None,
) -> list[SkillSpec]:
    """Resolve available runtime skills for prompt exposure."""
    requested_names = tuple(skill_names) if skill_names is not None else config.enabled_skills
    if config.skills_dir is None:
        if requested_names:
            raise RuntimeError("Skills were requested without configuring skills_dir")
        return []
    if not requested_names:
        return load_all_skills(config.skills_dir)
    return load_skills(config.skills_dir, requested_names)


def get_tools(
    config: AppConfig,
    *,
    skills: Sequence[SkillSpec] | None = None,
    skill_names: Sequence[str] | None = None,
) -> list:
    """Resolve runtime tools for the given config."""
    _ = skills, skill_names, config
    return get_builtin_tools()


def get_system_prompt(
    config: AppConfig,
    *,
    skills: Sequence[SkillSpec] | None = None,
    skill_names: Sequence[str] | None = None,
) -> str:
    """Resolve the final system prompt after skill composition."""
    resolved_skills = list(skills) if skills is not None else get_skills(config, skill_names=skill_names)
    return compose_system_prompt(config.system_prompt, resolved_skills)


def get_checkpointer(config: AppConfig):
    """Resolve the default checkpointer for the given config."""
    _ = config
    return get_default_checkpointer()


def get_state_schema():
    """Resolve the shared state schema for the lite runtime."""
    return ThreadState


__all__ = [
    "DisconnectMode",
    "MemoryStreamBridge",
    "REPLAY_GAP_EVENT",
    "RedisStreamBridge",
    "RunConflictError",
    "RunManager",
    "RunRecord",
    "RunStatus",
    "RunExecutor",
    "RunLifecycleHooks",
    "RuntimeService",
    "ClarificationRequest",
    "RuntimeExecutionResult",
    "RuntimeEvent",
    "RuntimeEventSink",
    "RuntimeJournal",
    "RuntimeUsageAccumulator",
    "RuntimeStreamEvent",
    "StreamBridge",
    "StreamEvent",
    "END_SENTINEL",
    "HEARTBEAT_SENTINEL",
    "TokenUsage",
    "get_checkpointer",
    "get_skills",
    "get_state_schema",
    "get_system_prompt",
    "get_tools",
    "invoke_agent_once",
    "normalize_token_usage",
]
