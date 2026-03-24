from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    openai_api_key: str = ""
    openai_base_url: str = ""
    model_name: str = "gpt-4.1-mini"
    embedding_model: str = "simple-hash"
    vector_db_dir: Path = Path(".cache/vectorstore")
    runtime_dir: Path = Path("./runtime")
    web_search_provider: str = "stub"
    use_stub_agents: bool = True

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        use_stub_default = not bool(openai_api_key)
        settings = cls(
            openai_api_key=openai_api_key,
            openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
            model_name=os.getenv("MODEL_NAME", "gpt-4.1-mini"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "simple-hash"),
            vector_db_dir=Path(os.getenv("VECTOR_DB_DIR", ".cache/vectorstore")),
            runtime_dir=Path(os.getenv("RUNTIME_DIR", "./runtime")),
            web_search_provider=os.getenv("WEB_SEARCH_PROVIDER", "stub"),
            use_stub_agents=_as_bool(os.getenv("USE_STUB_AGENTS"), use_stub_default),
        )
        if settings.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        return settings
