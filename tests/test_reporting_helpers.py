from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.builtins import run_builtin_subagent
from app.subagents.rendering import (
    ResearchNotes,
    WriterOutput,
    build_research_notes_from_state,
    build_writer_output_from_state,
    render_final_markdown,
    render_research_notes,
)


class ReportingHelpersTests(unittest.TestCase):
    def test_research_builder_uses_state_evidence_and_default_open_question(self) -> None:
        state = RunState(
            thread_id="thread-reporting",
            user_task="Summarize the available materials.",
            task_type="research_report",
            retrieved_docs=[{"source": "docs/02", "content": "Lead Agent delegates complex work."}],
        )

        notes = build_research_notes_from_state(state)

        self.assertEqual(notes.user_task, "Summarize the available materials.")
        self.assertIn("Task type: research_report", notes.key_findings)
        self.assertIn("Local retrieval was used.", notes.key_findings)
        self.assertEqual(notes.open_questions, [])
        self.assertIn("docs/02: Lead Agent delegates complex work.", notes.evidence)

    def test_research_renderer_preserves_section_structure(self) -> None:
        notes = ResearchNotes(
            user_task="Summarize the docs directory.",
            key_findings=[
                "The docs describe a Lead Agent plus subagent harness.",
                "Legacy workflow code still exists as a fallback.",
            ],
            evidence=[
                "docs/02-architecture-and-runtime.md",
                "docs/07-roadmap-and-progress.md",
            ],
            open_questions=["Which legacy pieces should be migrated first?"],
        )

        rendered = render_research_notes(notes)

        self.assertIn("# Research Notes", rendered)
        self.assertIn("## User task", rendered)
        self.assertIn("- The docs describe a Lead Agent plus subagent harness.", rendered)
        self.assertIn("1. docs/02-architecture-and-runtime.md", rendered)
        self.assertIn("## Open questions", rendered)

    def test_writer_builder_reads_notes_excerpt_from_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-reporting").create()
            workspace.write_text("notes/research.md", "# Research Notes\n\nKey point: shared rendering helpers.")
            state = RunState(
                thread_id="thread-reporting",
                user_task="Write the final report.",
                notes_files=["notes/research.md"],
            )

            output = build_writer_output_from_state(state, workspace)

            self.assertEqual(
                output.final_answer,
                "Generated a markdown report from the available task context and collected notes.",
            )
            self.assertIn("### Task\nWrite the final report.", output.sections)
            self.assertTrue(any("### Notes digest" in section for section in output.sections))

    def test_writer_renderer_preserves_final_report_structure(self) -> None:
        output = WriterOutput(
            final_answer="Generated a concise report.",
            sections=[
                "### Workflow\nThe run used explicit orchestration.",
                "### Summary\nThe task was completed.",
            ],
            evidence=["notes/research.md", "subagents/task_001/result.md"],
        )

        rendered = render_final_markdown(output)

        self.assertIn("# Final Report", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("### Workflow", rendered)
        self.assertIn("### Summary", rendered)
        self.assertIn("- notes/research.md", rendered)
        self.assertIn("- subagents/task_001/result.md", rendered)

    def test_builtin_subagent_artifact_includes_summary_and_prompt_excerpt(self) -> None:
        task = {
            "task_id": "task_123",
            "description": "Inspect docs",
            "prompt": "Read the workspace, identify the relevant files, and summarize the migration plan.",
            "subagent_type": "general-purpose",
        }

        result = run_builtin_subagent(task, "general-purpose", "General-purpose reasoning worker")

        self.assertEqual(result["artifact_path"], "subagents/task_123/result.md")
        self.assertIn("task_123", result["artifact_body"])
        self.assertIn("Inspect docs", result["artifact_body"])
        self.assertIn("General-purpose reasoning worker", result["artifact_body"])
        self.assertIn("Prompt focus:", result["artifact_body"])
        self.assertIn("migration plan", result["summary"])


if __name__ == "__main__":
    unittest.main()
