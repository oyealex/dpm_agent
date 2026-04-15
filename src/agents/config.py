from __future__ import annotations

import os
from pathlib import Path
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agents.sanitize import sanitize_text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "dpm-agent"
    debug: bool = False
    model: str = "openai:gpt-4.1"
    storage_backend: str = "sqlite"
    postgres_dsn: str | None = Field(default=None)
    db_path: Path = Field(default=Path("./data/agent.sqlite3"))
    sessions_dir: Path = Field(default=Path("./data/sessions"))
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = Field(default=None)
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = False
    cors_origins: str = ""
    cors_allow_credentials: bool = False
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"
    custom_env_prefixes: str = "AGENT_CUSTOM_,AGENT_AGENT_,AGENT_TOOL_"

    def ensure_directories(self) -> None:
        if self.effective_storage_backend == "sqlite":
            self.effective_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.effective_sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def effective_openai_base_url(self) -> str:
        return self.openai_base_url

    @property
    def effective_model_name(self) -> str:
        if self.model.startswith("openai:"):
            return self.model.removeprefix("openai:")
        return self.model

    @property
    def has_openai_api_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def effective_storage_backend(self) -> str:
        backend = sanitize_text(self.storage_backend).lower().strip()
        if backend in {"postgresql", "pg"}:
            return "postgres"
        if backend == "sqlite":
            return "sqlite"
        if backend == "postgres":
            return "postgres"
        return backend

    @property
    def effective_postgres_dsn(self) -> str | None:
        return self.postgres_dsn

    @property
    def effective_cors_origins(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def effective_cors_allow_methods(self) -> list[str]:
        return _split_csv(self.cors_allow_methods) or ["*"]

    @property
    def effective_cors_allow_headers(self) -> list[str]:
        return _split_csv(self.cors_allow_headers) or ["*"]

    @property
    def effective_db_path(self) -> Path:
        return self.db_path.expanduser().resolve()

    @property
    def effective_sessions_dir(self) -> Path:
        return self.sessions_dir.expanduser().resolve()

    @property
    def effective_custom_env_prefixes(self) -> list[str]:
        prefixes = _split_csv(self.custom_env_prefixes)
        cleaned: list[str] = []
        for prefix in prefixes:
            normalized = prefix.strip()
            if not normalized:
                continue
            if not normalized.endswith("_"):
                normalized = f"{normalized}_"
            cleaned.append(normalized.upper())
        return cleaned

    @property
    def effective_custom_env(self) -> dict[str, str]:
        return self.collect_custom_env()

    @property
    def effective_custom_agent_env(self) -> dict[str, str]:
        return self.collect_custom_env(prefixes=("AGENT_AGENT_",))

    @property
    def effective_custom_tool_env(self) -> dict[str, str]:
        return self.collect_custom_env(prefixes=("AGENT_TOOL_",))

    def collect_custom_env(self, prefixes: tuple[str, ...] | None = None) -> dict[str, str]:
        active_prefixes = (
            tuple(prefix.upper() for prefix in prefixes)
            if prefixes is not None
            else tuple(self.effective_custom_env_prefixes)
        )
        if not active_prefixes:
            return {}
        known_setting_env_keys = {
            f"AGENT_{name}".upper() for name in self.model_fields if name != "custom_env_prefixes"
        }
        custom_env: dict[str, str] = {}
        for key, value in os.environ.items():
            upper_key = key.upper()
            if upper_key in known_setting_env_keys:
                continue
            if any(upper_key.startswith(prefix) for prefix in active_prefixes):
                custom_env[upper_key] = sanitize_text(value)
        return custom_env

    def effective_session_dir(self, thread_id: str) -> Path:
        return (self.effective_sessions_dir / _safe_session_id(thread_id)).resolve()

    def effective_session_skills_dir(self, thread_id: str) -> Path:
        return self.effective_session_dir(thread_id) / "skills"

    def effective_session_memory_dir(self, thread_id: str) -> Path:
        return self.effective_session_dir(thread_id) / "memory"

    def ensure_session_directories(self, thread_id: str) -> Path:
        session_dir = self.effective_session_dir(thread_id)
        self._assert_inside_sessions_dir(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.effective_session_skills_dir(thread_id).mkdir(parents=True, exist_ok=True)
        self.effective_session_memory_dir(thread_id).mkdir(parents=True, exist_ok=True)
        return session_dir

    def _assert_inside_sessions_dir(self, path: Path) -> None:
        try:
            path.relative_to(self.effective_sessions_dir)
        except ValueError as exc:
            raise ValueError(
                f"Session path must be inside sessions dir {self.effective_sessions_dir}: {path}"
            ) from exc


def _safe_session_id(thread_id: str) -> str:
    thread_id = sanitize_text(thread_id)
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", thread_id).strip("._-")
    return cleaned or "default"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in sanitize_text(value).split(",") if item.strip()]
