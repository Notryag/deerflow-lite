from __future__ import annotations

from app.config.settings import Settings
from app.rag.retriever import RetrievalPipeline


def retrieve_knowledge(
    query: str,
    data_dir: str,
    settings: Settings,
    top_k: int = 3,
    collection_name: str | None = None,
) -> list[dict[str, object]]:
    pipeline = RetrievalPipeline(vector_db_dir=settings.vector_db_dir)
    return pipeline.retrieve(
        query=query,
        data_dir=data_dir,
        top_k=top_k,
        collection_name=collection_name or "default",
    )
