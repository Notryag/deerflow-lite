from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.agents.common import build_context
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.subagents.rendering import (
    ResearchNotes,
    WriterOutput,
    build_fallback_subagent_prompt,
    build_research_notes_from_state,
    build_writer_output_from_state,
    build_subagent_summary,
    render_final_markdown,
    render_research_notes,
    render_subagent_result_markdown,
)
from app.subagents.runner import run_subagent


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

    def test_research_builder_includes_subagent_summary(self) -> None:
        state = RunState(
            thread_id="thread-reporting",
            user_task="Summarize the available materials.",
            subagent_results=[{"task_id": "task_001", "summary": "The subagent inspected the workspace."}],
        )

        notes = build_research_notes_from_state(state)

        self.assertIn("Delegated subagent output was incorporated.", notes.key_findings)
        self.assertIn("The subagent inspected the workspace.", notes.evidence)

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

    def test_writer_builder_includes_subagent_results_and_artifacts(self) -> None:
        state = RunState(
            thread_id="thread-reporting",
            user_task="Write the final report.",
            subagent_results=[
                {
                    "task_id": "task_001",
                    "summary": "The subagent inspected the workspace.",
                    "artifacts": ["subagents/task_001/result.md"],
                }
            ],
        )

        output = build_writer_output_from_state(state)

        self.assertEqual(
            output.final_answer,
            "Generated a markdown report from delegated subagent output and collected runtime context.",
        )
        self.assertTrue(any("### Subagent results" in section for section in output.sections))
        self.assertIn("subagents/task_001/result.md", output.evidence)

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

    def test_subagent_runner_writes_artifact_from_agent_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-subagent").create()
            workspace.write_text("workspace/plan.md", "Migration plan")
            task = {
                "task_id": "task_123",
                "description": "Inspect docs",
                "prompt": "Read the workspace, identify the relevant files, and summarize the migration plan.",
                "subagent_type": "general-purpose",
                "runtime_tools": ["list_workspace_files", "read_file"],
                "runtime_context": {
                    "runtime_dir": str(Path(tmp)),
                    "thread_id": "thread-subagent",
                    "user_task": "Inspect docs",
                },
            }

            result = run_subagent(task, "general-purpose", "General-purpose reasoning worker", Settings())

            self.assertEqual(result["artifact_path"], "subagents/task_123/result.md")
            self.assertIn("task_123", result["artifact_body"])
            self.assertIn("Inspect docs", result["artifact_body"])
            self.assertIn("General-purpose reasoning worker", result["artifact_body"])
            self.assertIn("list_workspace_files", result["artifact_body"])
            self.assertIn("read_file", result["artifact_body"])
            self.assertIn("Completed the delegated task.", result["summary"])

    def test_shared_subagent_summary_and_artifact_renderer_are_consistent(self) -> None:
        task = {
            "task_id": "task_456",
            "description": "Inspect docs",
            "prompt": "Read the workspace, identify the relevant files, and summarize the migration plan.",
            "subagent_type": "general-purpose",
        }

        summary = build_subagent_summary(task, "general-purpose")
        artifact = render_subagent_result_markdown(task, "general-purpose", "General-purpose reasoning worker", summary)

        self.assertIn("general-purpose worker completed delegated task 'Inspect docs'.", summary)
        self.assertIn("Prompt focus:", summary)
        self.assertIn("task_456", artifact)
        self.assertIn("General-purpose reasoning worker", artifact)
        self.assertIn("Prompt", artifact)
        self.assertIn(summary, artifact)

    def test_fallback_subagent_prompt_includes_context_and_user_task(self) -> None:
        state = RunState(thread_id="thread-reporting", user_task="Summarize the docs directory.")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-reporting").create()
            prompt = build_fallback_subagent_prompt(
                state.user_task,
                context=build_context(state, workspace),
            )

        self.assertIn("Work only inside the shared workspace.", prompt)
        self.assertIn("Runtime context:", prompt)
        self.assertIn("User task:\nSummarize the docs directory.", prompt)


if __name__ == "__main__":
    unittest.main()
