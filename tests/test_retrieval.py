from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config.settings import Settings
from app.tools.retrieval import retrieve_knowledge


class RetrievalTests(unittest.TestCase):
    def test_retrieval_returns_structured_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "docs"
            data_dir.mkdir()
            (data_dir / "a.md").write_text("Python agent workflows and retrieval pipelines.", encoding="utf-8")

            settings = Settings(vector_db_dir=Path(tmp) / "vectors", runtime_dir=Path(tmp) / "runtime")
            results = retrieve_knowledge("retrieval pipelines", str(data_dir), settings=settings, top_k=2)

            self.assertGreaterEqual(len(results), 1)
            self.assertIn("content", results[0])
            self.assertIn("source", results[0])
            self.assertIn("score", results[0])
            self.assertIn("metadata", results[0])


if __name__ == "__main__":
    unittest.main()
