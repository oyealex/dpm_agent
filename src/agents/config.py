from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.sanitize import sanitize_text

DEFAULT_SETTINGS_PATH = Path("agents.yaml")
_ENV_REF_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class SettingsError(ValueError):
    """Raised when runtime settings are missing or invalid."""


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str = "sqlite"
    postgres_dsn: str | None = Field(default=None)
    db_path: Path = Field(default=Path("./data/agent.sqlite3"))
    sessions_dir: Path = Field(default=Path("./data/sessions"))


class CorsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origins: str = ""
    allow_credentials: bool = False
    allow_methods: str = "*"
    allow_headers: str = "*"


class StreamSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_event_name: bool = False
    include_assistant_message: bool = False


class ApiSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    cors: CorsSettings = Field(default_factory=CorsSettings)
    stream: StreamSettings = Field(default_factory=StreamSettings)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "agents"
    debug: bool = False
    default_user_id: str = "default"
    storage: StorageSettings = Field(default_factory=StorageSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)

    @classmethod
    def load(cls, config_path: Path | None = None, **overrides: Any) -> Settings:
        path = (config_path or DEFAULT_SETTINGS_PATH).expanduser().resolve()
        raw = _load_yaml_mapping(path)
        settings_section = raw.get("settings")
        if not isinstance(settings_section, dict):
            raise SettingsError(
                f"Agent config {path} must contain a top-level 'settings' mapping."
            )
        resolved = _resolve_env_references(settings_section, ("settings",))
        normalized = _normalize_settings_payload(resolved)
        try:
            return cls.model_validate({**normalized, **overrides})
        except ValidationError as exc:
            raise SettingsError(f"Invalid settings in {path}: {exc}") from exc

    def ensure_directories(self) -> None:
        if self.effective_storage_backend == "sqlite":
            self.effective_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.effective_sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def effective_storage_backend(self) -> str:
        backend = sanitize_text(self.storage.backend).lower().strip()
        return backend

    @property
    def effective_postgres_dsn(self) -> str | None:
        return self.storage.postgres_dsn

    @property
    def effective_cors_origins(self) -> list[str]:
        return _split_csv(self.api.cors.origins)

    @property
    def effective_cors_allow_methods(self) -> list[str]:
        return _split_csv(self.api.cors.allow_methods) or ["*"]

    @property
    def effective_cors_allow_headers(self) -> list[str]:
        return _split_csv(self.api.cors.allow_headers) or ["*"]

    @property
    def effective_db_path(self) -> Path:
        return self.storage.db_path.expanduser().resolve()

    @property
    def effective_sessions_dir(self) -> Path:
        return self.storage.sessions_dir.expanduser().resolve()

    @property
    def api_host(self) -> str:
        return self.api.host

    @property
    def api_port(self) -> int:
        return self.api.port

    @property
    def api_reload(self) -> bool:
        return self.api.reload

    @property
    def cors_allow_credentials(self) -> bool:
        return self.api.cors.allow_credentials

    @property
    def stream_include_event_name(self) -> bool:
        return self.api.stream.include_event_name

    @property
    def stream_include_assistant_message(self) -> bool:
        return self.api.stream.include_assistant_message

    @property
    def effective_default_user_id(self) -> str:
        return safe_path_id(self.default_user_id)

    def normalize_user_id(self, user_id: str | None = None) -> str:
        return safe_path_id(user_id or self.effective_default_user_id)

    def normalize_thread_id(self, thread_id: str | None = None) -> str:
        return safe_path_id(thread_id or "default")

    def runtime_thread_id(self, user_id: str, thread_id: str) -> str:
        user = self.normalize_user_id(user_id)
        thread = self.normalize_thread_id(thread_id)
        return f"{user}/{thread}"

    def effective_session_dir(self, user_id: str, thread_id: str) -> Path:
        return (
            self.effective_sessions_dir
            / self.normalize_user_id(user_id)
            / self.normalize_thread_id(thread_id)
        ).resolve()

    def effective_session_skills_dir(self, user_id: str, thread_id: str) -> Path:
        return self.effective_session_dir(user_id, thread_id) / "skills"

    def effective_session_memory_dir(self, user_id: str, thread_id: str) -> Path:
        return self.effective_session_dir(user_id, thread_id) / "memory"

    def ensure_session_directories(self, user_id: str, thread_id: str) -> Path:
        session_dir = self.effective_session_dir(user_id, thread_id)
        self._assert_inside_sessions_dir(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.effective_session_skills_dir(user_id, thread_id).mkdir(parents=True, exist_ok=True)
        self.effective_session_memory_dir(user_id, thread_id).mkdir(parents=True, exist_ok=True)
        return session_dir

    def _assert_inside_sessions_dir(self, path: Path) -> None:
        try:
            path.relative_to(self.effective_sessions_dir)
        except ValueError as exc:
            raise ValueError(
                f"Session path must be inside sessions dir {self.effective_sessions_dir}: {path}"
            ) from exc


def safe_path_id(value: str | None, default: str = "default") -> str:
    value = sanitize_text(value or default)
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return cleaned or "default"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in sanitize_text(value).split(",") if item.strip()]


def _load_yaml_mapping(config_path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"Settings file does not exist: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise SettingsError(f"Invalid YAML in settings file {config_path}: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise SettingsError("Settings file must be a YAML mapping.")
    return loaded


def _resolve_env_references(value: Any, key_path: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_env_references(item, (*key_path, str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_env_references(item, key_path) for item in value]
    if isinstance(value, str):
        match = _ENV_REF_RE.match(value)
        if match:
            env_name = match.group(1)
            if env_name not in os.environ:
                key = ".".join(key_path) if key_path else "<root>"
                raise SettingsError(
                    f"Environment variable '{env_name}' is not set for settings key '{key}'."
                )
            return sanitize_text(os.environ[env_name])
    return value


def _normalize_settings_payload(raw_settings: dict[str, Any]) -> dict[str, Any]:
    # 兼容旧版平铺 settings，同时统一归一到分组结构：
    # storage / api / api.cors / api.stream。
    normalized = dict(raw_settings)

    if "storage" not in normalized:
        normalized["storage"] = {
            "backend": normalized.pop("storage_backend", "sqlite"),
            "postgres_dsn": normalized.pop("postgres_dsn", None),
            "db_path": normalized.pop("db_path", Path("./data/agent.sqlite3")),
            "sessions_dir": normalized.pop("sessions_dir", Path("./data/sessions")),
        }

    if "api" not in normalized:
        normalized["api"] = {
            "host": normalized.pop("api_host", "127.0.0.1"),
            "port": normalized.pop("api_port", 8000),
            "reload": normalized.pop("api_reload", False),
            "cors": {
                "origins": normalized.pop("cors_origins", ""),
                "allow_credentials": normalized.pop("cors_allow_credentials", False),
                "allow_methods": normalized.pop("cors_allow_methods", "*"),
                "allow_headers": normalized.pop("cors_allow_headers", "*"),
            },
            "stream": {
                "include_event_name": normalized.pop("stream_include_event_name", False),
                "include_assistant_message": normalized.pop("stream_include_assistant_message", False),
            },
        }

    return normalized
