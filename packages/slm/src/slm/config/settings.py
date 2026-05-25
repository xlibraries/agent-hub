from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
