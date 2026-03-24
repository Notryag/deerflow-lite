from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config.settings import Settings
from app.runtime.state import RunState
from app.runtime.workspace import Workspace


@dataclass(slots=True)
class AgentContext:
    task_summary: str
    state_summary: str
    workspace_summary: str
    retrieved_summary: str
    search_summary: str


def build_context(state: RunState, workspace: Workspace) -> AgentContext:
    state_summary = (
        f"task_type={state.task_type or 'unknown'}; "
        f"needs_retrieval={state.needs_retrieval}; "
        f"needs_web_search={state.needs_web_search}; "
        f"needs_python={state.needs_python}; "
        f"retrieved_docs={len(state.retrieved_docs)}; "
        f"search_results={len(state.search_results)}"
    )
    return AgentContext(
        task_summary=state.user_task,
        state_summary=state_summary,
        workspace_summary=workspace.summarize(),
        retrieved_summary=_summarize_items(state.retrieved_docs, content_key="content"),
        search_summary=_summarize_items(state.search_results, content_key="snippet"),
    )


def use_stub_agents(settings: Settings) -> bool:
    return settings.use_stub_agents or not settings.openai_api_key


def format_context_block(context: AgentContext) -> str:
    return (
        "Runtime context:\n"
        f"- task: {context.task_summary}\n"
        f"- state: {context.state_summary}\n"
        f"- workspace:\n{context.workspace_summary}\n"
        f"- retrieved materials:\n{context.retrieved_summary}\n"
        f"- web results:\n{context.search_summary}"
    )


def normalize_bullets(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def shorten_text(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def extract_evidence(items: list[dict[str, Any]], limit: int = 3) -> list[str]:
    evidence: list[str] = []
    for item in items[:limit]:
        source = str(item.get("source", "unknown"))
        content = shorten_text(str(item.get("content") or item.get("snippet") or ""))
        evidence.append(f"{source}: {content}")
    return evidence


def _summarize_items(items: list[dict[str, Any]], content_key: str, limit: int = 3) -> str:
    if not items:
        return "none"
    lines: list[str] = []
    for item in items[:limit]:
        source = str(item.get("source", "unknown"))
        content = shorten_text(str(item.get(content_key, "")), limit=180)
        lines.append(f"- {source}: {content}")
    return "\n".join(lines)


def build_chat_model(settings: Settings):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url or None,
        temperature=0,
    )
