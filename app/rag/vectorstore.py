from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.rag.embeddings import SimpleEmbeddingModel
from app.rag.splitter import TextChunk


@dataclass(slots=True)
class VectorRecord:
    content: str
    source: str
    metadata: dict[str, str]
    vector: list[float]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


class LocalVectorStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def index(self, chunks: list[TextChunk], embedder: SimpleEmbeddingModel) -> list[VectorRecord]:
        records = [
            VectorRecord(
                content=chunk.content,
                source=chunk.source,
                metadata=chunk.metadata,
                vector=embedder.embed(chunk.content),
            )
            for chunk in chunks
        ]
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return records

    def load(self) -> list[VectorRecord]:
        if not self.file_path.exists():
            return []
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        return [VectorRecord(**item) for item in payload]

    def similarity_search(
        self,
        query: str,
        embedder: SimpleEmbeddingModel,
        top_k: int = 3,
    ) -> list[dict[str, object]]:
        query_vector = embedder.embed(query)
        scored = []
        for record in self.load():
            score = _cosine_similarity(query_vector, record.vector)
            scored.append(
                {
                    "content": record.content,
                    "source": record.source,
                    "score": round(score, 4),
                    "metadata": record.metadata,
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]
