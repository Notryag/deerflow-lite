from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents.common import AgentContext, extract_evidence, format_context_block, normalize_bullets
from app.runtime.state import RunState
from app.runtime.workspace import Workspace

RESEARCH_BASE_PROMPT = (
    "Write structured research notes from the available materials. "
    "Keep findings concise and include open questions for missing information."
)

WRITER_BASE_PROMPT = (
    "Write a concise final markdown report. "
    "Distinguish facts grounded in retrieved material from synthesis."
)

LEAD_BASE_PROMPT = (
    "You are the DeerFlow Lite lead agent. "
    "Decide whether to answer directly or delegate by calling the task tool. "
    "Use the task tool for complex, multi-step work that benefits from isolated context. "
    "Do not delegate simple single-step requests. "
    "After any tool use, produce a concise final answer."
)

FALLBACK_SUBAGENT_BASE_PROMPT = (
    "Work only inside the shared workspace. "
    "Review the available runtime context, retrieved materials, and web results if present. "
    "Return a concise summary for the parent agent and write a result artifact."
)


class ResearchNotes(BaseModel):
    user_task: str
    key_findings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class WriterOutput(BaseModel):
    final_answer: str
    sections: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


def render_research_notes(notes: ResearchNotes) -> str:
    finding_lines = "\n".join(f"- {item}" for item in notes.key_findings) or "- No findings."
    evidence_lines = "\n".join(f"{idx}. {item}" for idx, item in enumerate(notes.evidence, start=1)) or "1. No evidence."
    question_lines = "\n".join(f"- {item}" for item in notes.open_questions) or "- None."
    return (
        "# Research Notes\n\n"
        f"## User task\n{notes.user_task}\n\n"
        f"## Key findings\n{finding_lines}\n\n"
        f"## Evidence\n{evidence_lines}\n\n"
        f"## Open questions\n{question_lines}\n"
    )


def render_final_markdown(output: WriterOutput) -> str:
    body = "\n\n".join(output.sections) if output.sections else "No report body was generated."
    evidence = "\n".join(f"- {item}" for item in output.evidence) or "- No cited evidence."
    return (
        "# Final Report\n\n"
        f"## Summary\n{output.final_answer}\n\n"
        f"## Report\n{body}\n\n"
        f"## Evidence\n{evidence}\n"
    )


def build_prompt_with_context(base_prompt: str, context: AgentContext) -> str:
    return f"{base_prompt}\n\n{format_context_block(context)}"


def build_research_prompt(context: AgentContext) -> str:
    return build_prompt_with_context(RESEARCH_BASE_PROMPT, context)


def build_writer_prompt(context: AgentContext) -> str:
    return build_prompt_with_context(WRITER_BASE_PROMPT, context)


def build_lead_prompt(context: AgentContext) -> str:
    return build_prompt_with_context(LEAD_BASE_PROMPT, context)


def build_fallback_subagent_prompt(user_task: str, context: AgentContext) -> str:
    return (
        f"{build_prompt_with_context(FALLBACK_SUBAGENT_BASE_PROMPT, context)}\n\n"
        f"User task:\n{user_task}"
    )


def build_research_notes_from_state(state: RunState) -> ResearchNotes:
    findings = normalize_bullets(
        [
            f"Task type: {state.task_type or 'research_report'}",
            "Local retrieval was used." if state.retrieved_docs else "",
            "Web search was used." if state.search_results else "",
            "Delegated subagent output was incorporated." if state.subagent_results else "",
            "The workflow is running with explicit orchestration and file outputs.",
        ]
    )
    evidence = extract_evidence(state.retrieved_docs) + extract_evidence(state.search_results)
    evidence.extend(str(item.get("summary", "")).strip() for item in state.subagent_results if str(item.get("summary", "")).strip())
    open_questions = [] if evidence else ["No external evidence was available; output is based on task and workflow defaults."]
    return ResearchNotes(
        user_task=state.user_task,
        key_findings=findings,
        evidence=evidence,
        open_questions=open_questions,
    )


def build_writer_output_from_state(state: RunState, workspace: Workspace | None = None) -> WriterOutput:
    notes_excerpt = ""
    if workspace is not None and state.notes_files:
        notes_excerpt = workspace.read_text(state.notes_files[0])[:500].strip()
    sections = [
        "### Workflow\nThis run used an explicit workflow, file-backed workspace, and structured state transitions.",
        f"### Task\n{state.user_task}",
    ]
    if notes_excerpt:
        sections.append(f"### Notes digest\n{notes_excerpt}")
    if state.subagent_results:
        lines = []
        for item in state.subagent_results:
            task_id = str(item.get("task_id", "unknown"))
            summary = str(item.get("summary", "")).strip() or str(item.get("status", "unknown"))
            lines.append(f"- `{task_id}`: {summary}")
        sections.append("### Subagent results\n" + "\n".join(lines))
    evidence = extract_evidence(state.retrieved_docs) + extract_evidence(state.search_results)
    evidence.extend(str(artifact) for item in state.subagent_results for artifact in item.get("artifacts", []))
    summary = "Generated a markdown report from the available task context and collected notes."
    if state.retrieved_docs:
        summary = "Generated a markdown report using retrieved local context and structured research notes."
    if state.subagent_results:
        summary = "Generated a markdown report from delegated subagent output and collected runtime context."
    return WriterOutput(final_answer=summary, sections=sections, evidence=evidence)


def build_subagent_summary(task: dict[str, Any], spec_name: str) -> str:
    description = str(task.get("description", "")).strip()
    prompt = str(task.get("prompt", "")).strip()
    prompt_excerpt = prompt[:160].strip()
    if len(prompt) > 160:
        prompt_excerpt += "..."
    tool_names = [str(item) for item in task.get("runtime_tools", []) if str(item).strip()]
    tool_suffix = ""
    if tool_names:
        tool_suffix = f" Available tools: {', '.join(tool_names)}."
    executed = [str(item) for item in task.get("executed_tools", []) if str(item).strip()]
    executed_suffix = ""
    if executed:
        executed_suffix = f" Executed tools: {', '.join(executed)}."
    return (
        f"{spec_name} worker completed delegated task '{description}'. "
        f"Prompt focus: {prompt_excerpt}.{tool_suffix}{executed_suffix}"
    )


def build_delegated_final_answer() -> str:
    return "Completed the task via a delegated subagent."


def build_delegated_final_sections(
    user_task: str,
    task_id: str,
    subagent_type: str,
    result_summary: str,
) -> list[str]:
    return [
        f"### Task\n{user_task}",
        f"### Delegation\nCreated subagent task `{task_id}` of type `{subagent_type}`.",
        f"### Result\n{result_summary}",
    ]


def render_subagent_result_markdown(
    task: dict[str, Any],
    spec_name: str,
    spec_description: str,
    summary: str,
) -> str:
    tool_lines = ", ".join(str(item) for item in task.get("runtime_tools", []) if str(item).strip()) or "none"
    execution_lines = (
        "\n".join(f"- {item}" for item in task.get("tool_observations", []) if str(item).strip())
        or "- none"
    )
    return (
        "# Subagent Result\n\n"
        f"## Task ID\n{task['task_id']}\n\n"
        f"## Description\n{task['description']}\n\n"
        f"## Subagent Type\n{task['subagent_type']}\n\n"
        f"## Type Notes\n{spec_description}\n\n"
        f"## Runtime Tools\n{tool_lines}\n\n"
        f"## Tool Execution\n{execution_lines}\n\n"
        f"## Worker\n{spec_name}\n\n"
        f"## Prompt\n{task['prompt']}\n\n"
        f"## Summary\n{summary}\n"
    )
