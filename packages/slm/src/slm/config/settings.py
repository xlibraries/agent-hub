from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SLM_",
        extra="ignore",
    )

    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    default_model: str = Field(default="qwen2.5-coder:14b")
    log_format: str = Field(default="console")
    log_level: str = Field(default="INFO")
    max_retries: int = Field(default=3)
    request_timeout_s: float = Field(default=120.0)
    kill_switch_env: str = Field(
        default="SLM_KILL_SWITCH",
        description="Environment variable name; if set to 1/true, abort autonomous loops.",
    )
    experiments_enabled: bool = Field(default=True)
    experiments_db_path: Path = Field(
        default=Path(".agent-hub/experiments.db"),
        description="SQLite database for local experiment tracking.",
    )
    sessions_db_path: Path = Field(
        default=Path(".agent-hub/sessions.db"),
        description="SQLite database for conversation persistence.",
    )
    prompts_dir: Path = Field(
        default=Path(".agent-hub/prompts"),
        description="Directory with prompt override files (<key>.md).",
    )
    otel_enabled: bool | None = Field(
        default=None,
        description="Force OTEL on/off; when unset, enabled if SLM_OTEL_EXPORTER is set.",
    )
    otel_exporter: str = Field(
        default="none",
        description="Trace exporter: none | console | otlp",
    )
    otel_service_name: str = Field(default="agent-hub-slm")
    context_max_chars: int = Field(default=24_000)
    context_diff_max_chars: int = Field(default=8_000)
    context_readme_max_chars: int = Field(default=6_000)
    context_manifest_max_chars: int = Field(default=2_000)
    context_tree_max_entries: int = Field(default=120)
    context_tree_max_depth: int = Field(default=2)
    tool_max_read_bytes: int = Field(default=64_000)
    tool_grep_max_matches: int = Field(default=50)
    tool_grep_max_files: int = Field(default=200)
    executor_max_steps: int = Field(
        default=5,
        description="Maximum plan→execute→verify iterations per agent run.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
