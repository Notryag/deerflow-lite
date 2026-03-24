from __future__ import annotations

from dataclasses import dataclass

from app.rag.loaders import LoadedDocument


@dataclass(slots=True)
class TextChunk:
    content: str
    source: str
    metadata: dict[str, str]


def split_documents(
    documents: list[LoadedDocument],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[TextChunk]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    chunks: list[TextChunk] = []
    step = chunk_size - chunk_overlap
    for document in documents:
        text = document.content.strip()
        if not text:
            continue
        for index, start in enumerate(range(0, len(text), step)):
            chunk = text[start : start + chunk_size].strip()
            if not chunk:
                continue
            metadata = dict(document.metadata)
            metadata["chunk_index"] = str(index)
            chunks.append(TextChunk(content=chunk, source=document.source, metadata=metadata))
    return chunks
