from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.state import RunState
from app.runtime.workspace import Workspace
from app.tools.reporting import write_final_report, write_research_notes


class ReportingToolTests(unittest.TestCase):
    def test_write_research_notes_persists_artifact_and_updates_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-reporting-tool").create()
            state = RunState(
                thread_id="thread-reporting-tool",
                user_task="Summarize the local documents.",
                task_type="research_report",
                retrieved_docs=[{"source": "docs/02", "content": "Lead Agent delegates complex work."}],
            )

            notes = write_research_notes(state, workspace)

            self.assertEqual(notes.user_task, "Summarize the local documents.")
            self.assertIn("notes/research.md", state.notes_files)
            self.assertIn("notes/research.md", state.artifact_files)
            self.assertTrue((workspace.thread_dir / "notes" / "research.md").exists())

    def test_write_final_report_reads_notes_and_updates_final_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-reporting-tool").create()
            workspace.write_text("notes/research.md", "# Research Notes\n\nKey point: tools own capabilities.")
            state = RunState(
                thread_id="thread-reporting-tool",
                user_task="Write the final report.",
                notes_files=["notes/research.md"],
            )

            output = write_final_report(state, workspace)

            self.assertEqual(state.final_answer, output.final_answer)
            self.assertIn("outputs/final.md", state.output_files)
            self.assertIn("outputs/final.md", state.artifact_files)
            self.assertTrue((workspace.thread_dir / "outputs" / "final.md").exists())


if __name__ == "__main__":
    unittest.main()
