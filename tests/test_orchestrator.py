from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.agents.orchestrator import OrchestratorAgent
from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


class OrchestratorTests(unittest.TestCase):
    def test_orchestrator_decides_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp), "thread-1").create()
            settings = Settings(runtime_dir=Path(tmp), use_stub_agents=True)
            agent = OrchestratorAgent(settings)
            state = RunState(thread_id="thread-1", user_task="Summarize the docs directory into a report")

            updated = agent.run(state, workspace)

            self.assertTrue(updated.needs_retrieval)
            self.assertGreaterEqual(len(updated.plan), 2)


if __name__ == "__main__":
    unittest.main()
