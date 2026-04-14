from __future__ import annotations

import os
from pathlib import Path
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from dpm_agent.sanitize import sanitize_text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DPM_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "dpm-agent"
    model: str = "openai:gpt-4.1"
    system_prompt: str = "你是我的个人 Agent。"
    db_path: Path = Field(default=Path("./data/agent.sqlite3"))
    sessions_dir: Path = Field(default=Path("./data/sessions"))
    openai_base_url: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)

    def ensure_directories(self) -> None:
        self.effective_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.effective_sessions_dir.mkdir(parents=True, exist_ok=True)

    def apply_provider_environment(self) -> None:
        if self.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = self.openai_base_url
        elif os.getenv("OPENAI_API_BASE") and not os.getenv("OPENAI_BASE_URL"):
            os.environ["OPENAI_BASE_URL"] = os.getenv("OPENAI_API_BASE", "")
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key

    @property
    def effective_openai_base_url(self) -> str:
        return (
            self.openai_base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or "https://api.openai.com/v1"
        )

    @property
    def effective_model_name(self) -> str:
        if self.model.startswith("openai:"):
            return self.model.removeprefix("openai:")
        return self.model

    @property
    def has_openai_api_key(self) -> bool:
        return bool(self.openai_api_key or os.getenv("OPENAI_API_KEY"))

    @property
    def effective_db_path(self) -> Path:
        return self.db_path.expanduser().resolve()

    @property
    def effective_sessions_dir(self) -> Path:
        return self.sessions_dir.expanduser().resolve()

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
