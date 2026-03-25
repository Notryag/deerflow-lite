from __future__ import annotations

from typing import Any

from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.registry import SubagentRegistry


class TaskTool:
    def __init__(
        self,
        state: RunState,
        workspace: Workspace,
        registry: SubagentRegistry | None = None,
    ) -> None:
        self.state = state
        self.workspace = workspace
        self.registry = registry or SubagentRegistry()

    def create_task(
        self,
        description: str,
        prompt: str,
        subagent_type: str = "general-purpose",
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        cleaned_description = description.strip()
        cleaned_prompt = prompt.strip()
        if not cleaned_description:
            raise ValueError("description must not be empty")
        if not cleaned_prompt:
            raise ValueError("prompt must not be empty")

        spec = self.registry.get(subagent_type)
        resolved_max_turns = self.registry.resolve_max_turns(subagent_type, max_turns)
        task_id = f"task_{len(self.state.subagent_tasks) + 1:03d}"

        task = {
            "task_id": task_id,
            "description": cleaned_description,
            "subagent_type": spec.name,
            "status": "pending",
            "prompt": cleaned_prompt,
            "max_turns": resolved_max_turns,
            "timeout_seconds": spec.timeout_seconds,
            "allowed_tools": list(spec.allowed_tools),
            "disallowed_tools": list(spec.disallowed_tools),
        }
        self.state.record_subagent_task(**task)
        self.workspace.append_manifest_task(task)

        return {
            "task_id": task_id,
            "description": cleaned_description,
            "subagent_type": spec.name,
            "status": "pending",
            "summary": "",
            "artifacts": [],
            "citations": [],
            "error": None,
        }
