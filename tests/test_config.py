import pytest
from north.config import AppConfig


def test_from_env_parses_skill_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODEL_NAME", "openai:gpt-4o-mini")
    monkeypatch.setenv("APP_SKILLS_DIR", str(tmp_path))
    monkeypatch.setenv("APP_SKILLS", "research, writer, research")
    monkeypatch.setenv("APP_THREAD_BASE_DIR", str(tmp_path / "threads-data"))

    config = AppConfig.from_env()

    assert config.skills_dir == tmp_path
    assert config.thread_base_dir == tmp_path / "threads-data"
    assert config.enabled_skills == ("research", "writer")


def test_from_env_parses_run_aware_summarization_settings(monkeypatch) -> None:
    monkeypatch.setenv("APP_SUMMARIZATION_NORMAL_TRIGGER_TOKENS", "6000")
    monkeypatch.setenv("APP_SUMMARIZATION_EMERGENCY_TRIGGER_TOKENS", "12000")
    monkeypatch.setenv("APP_SUMMARIZATION_MESSAGE_CEILING", "60")
    monkeypatch.setenv("APP_SUMMARIZATION_TARGET_TOKENS", "2000")
    monkeypatch.setenv("APP_SUMMARIZATION_MIN_GROWTH_TOKENS", "3000")
    monkeypatch.setenv("APP_SUMMARIZATION_MAX_EMERGENCY_COMPACTIONS", "2")

    config = AppConfig.from_env()

    assert config.summarization_normal_trigger_tokens == 6000
    assert config.summarization_emergency_trigger_tokens == 12000
    assert config.summarization_message_ceiling == 60
    assert config.summarization_target_tokens == 2000
    assert config.summarization_min_growth_tokens == 3000
    assert config.summarization_max_emergency_compactions == 2


def test_from_env_parses_auto_title_settings(monkeypatch) -> None:
    monkeypatch.setenv("APP_AUTO_TITLE_ENABLED", "true")
    monkeypatch.setenv("APP_TITLE_MODEL_NAME", "openai:gpt-4o-mini")
    monkeypatch.setenv("APP_TITLE_MAX_CHARS", "32")

    config = AppConfig.from_env()

    assert config.auto_title_enabled is True
    assert config.title_model_name == "openai:gpt-4o-mini"
    assert config.title_max_chars == 32


def test_from_env_uses_explicit_host_path_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_SKILLS_DIR", raising=False)
    monkeypatch.delenv("APP_THREAD_BASE_DIR", raising=False)

    config = AppConfig.from_env(
        skills_dir=tmp_path / "skills",
        thread_base_dir=tmp_path / "runtime-data",
    )

    assert config.skills_dir == tmp_path / "skills"
    assert config.thread_base_dir == tmp_path / "runtime-data"


def test_validate_requires_langsmith_api_key_when_tracing_enabled(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY is not set"):
        AppConfig(model_name="openai:gpt-4o-mini").validate()


def test_validate_allows_langsmith_when_api_key_is_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")

    AppConfig(model_name="openai:gpt-4o-mini").validate()


def test_validate_requires_existing_skills_dir_when_skills_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    missing_dir = tmp_path / "missing-skills"

    with pytest.raises(RuntimeError, match="skills directory does not exist"):
        AppConfig(
            model_name="openai:gpt-4o-mini",
            skills_dir=missing_dir,
            enabled_skills=("research",),
        ).validate()
