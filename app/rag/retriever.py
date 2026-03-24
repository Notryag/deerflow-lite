from __future__ import annotations

from pathlib import Path

from app.rag.embeddings import SimpleEmbeddingModel
from app.rag.loaders import load_documents
from app.rag.splitter import split_documents
from app.rag.vectorstore import LocalVectorStore


class RetrievalPipeline:
    def __init__(self, vector_db_dir: Path) -> None:
        self.vector_db_dir = vector_db_dir
        self.embedder = SimpleEmbeddingModel()

    def _collection_path(self, collection_name: str) -> Path:
        return self.vector_db_dir / f"{collection_name}.json"

    def build_index(self, data_dir: str | Path, collection_name: str) -> LocalVectorStore:
        documents = load_documents(data_dir)
        chunks = split_documents(documents)
        store = LocalVectorStore(self._collection_path(collection_name))
        store.index(chunks, self.embedder)
        return store

    def retrieve(
        self,
        query: str,
        data_dir: str | Path,
        top_k: int = 3,
        collection_name: str = "default",
    ) -> list[dict[str, object]]:
        store = LocalVectorStore(self._collection_path(collection_name))
        if not store.file_path.exists():
            store = self.build_index(data_dir, collection_name)
        return store.similarity_search(query=query, embedder=self.embedder, top_k=top_k)
