"""
AgentForge — Central Configuration
All settings loaded from environment variables / .env file.
"""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = "gemini"          # gemini | openai | anthropic | openai_compatible
    llm_model: str = "gemini-3.7-flash"
    llm_api_key: str = ""
    llm_base_url: str = ""                # for openai_compatible
    llm_planner_model: str = "gemini-3.7-flash"

    # ── URL Shortener ─────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./agentforge_urlshortener.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False
    base_url: str = "http://localhost:8000"
    short_code_length: int = 7

    # ── AgentForge System ─────────────────────────────────────────────────────
    reference_repo_path: str = "./reference_app/url_shortener"
    max_remediation_retries: int = 2
    workflow_db_path: str = "./agentforge_workflow.db"

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    @property
    def reference_repo_abs_path(self) -> Path:
        return Path(self.reference_repo_path).resolve()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
