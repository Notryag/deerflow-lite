from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


@dataclass(slots=True)
class LoadedDocument:
    content: str
    source: str
    metadata: dict[str, str]


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support requires pypdf to be installed.") from exc
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_documents(data_dir: str | Path) -> list[LoadedDocument]:
    root = Path(data_dir)
    if not root.exists():
        raise FileNotFoundError(f"data directory not found: {root}")
    paths = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES]
    documents: list[LoadedDocument] = []
    for path in sorted(paths):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            content = _load_pdf(path)
        else:
            content = path.read_text(encoding="utf-8")
        documents.append(
            LoadedDocument(
                content=content,
                source=str(path),
                metadata={"filename": path.name, "suffix": suffix},
            )
        )
    return documents
