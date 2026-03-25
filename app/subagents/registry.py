from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubagentSpec:
    name: str
    description: str
    max_turns: int
    timeout_seconds: int
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...] = ("task",)


class SubagentRegistry:
    def __init__(self, specs: list[SubagentSpec] | None = None) -> None:
        entries = specs or self._default_specs()
        self._specs = {spec.name: spec for spec in entries}

    def list_types(self) -> list[str]:
        return sorted(self._specs)

    def get(self, subagent_type: str) -> SubagentSpec:
        try:
            return self._specs[subagent_type]
        except KeyError as exc:
            supported = ", ".join(self.list_types())
            raise ValueError(f"unknown subagent_type '{subagent_type}'; supported: {supported}") from exc

    def resolve_max_turns(self, subagent_type: str, requested: int | None) -> int:
        spec = self.get(subagent_type)
        if requested is None:
            return spec.max_turns
        if requested <= 0:
            raise ValueError("max_turns must be greater than 0")
        if requested > spec.max_turns:
            raise ValueError(
                f"max_turns {requested} exceeds limit {spec.max_turns} for subagent_type '{subagent_type}'"
            )
        return requested

    @staticmethod
    def _default_specs() -> list[SubagentSpec]:
        return [
            SubagentSpec(
                name="general-purpose",
                description="General research and synthesis worker.",
                max_turns=8,
                timeout_seconds=900,
                allowed_tools=(
                    "retrieve_knowledge",
                    "search_web",
                    "read_file",
                    "write_file",
                    "list_workspace_files",
                ),
            ),
            SubagentSpec(
                name="bash",
                description="Shell-oriented worker with a narrower tool surface.",
                max_turns=6,
                timeout_seconds=900,
                allowed_tools=(
                    "read_file",
                    "write_file",
                    "list_workspace_files",
                    "run_python_code",
                ),
            ),
        ]
