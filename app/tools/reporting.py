from __future__ import annotations

from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import (
    WriterOutput,
    ResearchNotes,
    build_research_notes_from_state,
    build_writer_output_from_state,
    render_final_markdown,
    render_research_notes,
)


def write_research_notes(state: RunState, workspace: Workspace) -> ResearchNotes:
    notes = build_research_notes_from_state(state)
    path = workspace.write_text("notes/research.md", render_research_notes(notes))
    relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
    if relative not in state.notes_files:
        state.notes_files.append(relative)
    state.add_artifact_file(relative)
    return notes


def write_final_report(state: RunState, workspace: Workspace) -> WriterOutput:
    output = build_writer_output_from_state(state, workspace)
    path = workspace.write_text("outputs/final.md", render_final_markdown(output))
    relative = str(path.relative_to(workspace.thread_dir)).replace("\\", "/")
    if relative not in state.output_files:
        state.output_files.append(relative)
    state.add_artifact_file(relative)
    state.final_answer = output.final_answer
    return output
