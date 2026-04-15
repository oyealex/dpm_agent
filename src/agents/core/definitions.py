from __future__ import annotations

import importlib
import os
import re
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agents.core.tools import AgentToolProvider
from agents.sanitize import sanitize_text

DEFAULT_SYSTEM_PROMPT = "你是我的个人 Agent。"
DEFAULT_AGENT_CONFIG_PATH = Path("agents.yaml")
_ENV_REF_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}$")
_SECRET_KEYS = ("key", "secret", "token", "password", "dsn", "credential")


class AgentConfigError(ValueError):
    """Raised when an agent configuration file is invalid."""


@dataclass(frozen=True)
class LlmResource:
    name: str
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResourceToggle:
    enabled: bool = True
    paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class AgentDefinition:
    """Declarative agent profile for pluggable multi-agent runtime bootstrapping."""

    name: str
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    llm: LlmResource | None = None
    skills: AgentResourceToggle = field(default_factory=AgentResourceToggle)
    memory: AgentResourceToggle = field(default_factory=AgentResourceToggle)
    include_builtin_tools: bool = True
    tool_providers: tuple[AgentToolProvider, ...] = ()
    subagent_names: tuple[str, ...] = ()
    create_kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def include_skills(self) -> bool:
        return self.skills.enabled

    @property
    def include_memory(self) -> bool:
        return self.memory.enabled


class AgentRegistry:
    """Registry for agent definitions that can be addressed by name from CLI/API."""

    def __init__(self, definitions: Iterable[AgentDefinition]) -> None:
        entries = {item.name: item for item in definitions}
        if not entries:
            raise ValueError("At least one agent definition is required.")
        self._entries = entries

    def get(self, name: str) -> AgentDefinition:
        key = name.strip()
        if key not in self._entries:
            available = ", ".join(sorted(self._entries))
            raise ValueError(f"Unknown agent '{name}'. Available: {available}")
        return self._entries[key]

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def merged_with(self, definitions: Iterable[AgentDefinition]) -> AgentRegistry:
        entries = dict(self._entries)
        for definition in definitions:
            entries[definition.name] = definition
        return AgentRegistry(entries.values())


DEFAULT_AGENT_REGISTRY = AgentRegistry(
    (
        AgentDefinition(name="default", system_prompt=DEFAULT_SYSTEM_PROMPT),
        AgentDefinition(
            name="db_explorer",
            system_prompt=(
                "你是一个数据库探索 Agent。优先通过工具查看 schema 和数据，"
                "再给出结论；避免假设不存在的表结构。"
            ),
        ),
    )
)


class LlmResourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ToolResourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    config: dict[str, Any] = Field(default_factory=dict)


class ToggleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    paths: list[Path] = Field(default_factory=list)


class AgentResourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    llm: str | None = None
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    system_prompt_file: Path | None = None
    skills: bool | ToggleConfig = True
    memory: bool | ToggleConfig = True
    include_builtin_tools: bool = True
    subagents: list[str] = Field(default_factory=list)
    create_kwargs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_prompt_sources(self) -> AgentResourceConfig:
        if self.system_prompt is not None and self.system_prompt_file is not None:
            raise ValueError("system_prompt and system_prompt_file cannot both be set")
        return self


class AgentConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llms: list[LlmResourceConfig]
    tools: list[ToolResourceConfig]
    agents: list[AgentResourceConfig]


def discover_agent_config_path(config_path: Path | None = None) -> tuple[Path | None, bool]:
    if config_path is not None:
        return config_path.expanduser().resolve(), True
    default_path = DEFAULT_AGENT_CONFIG_PATH.resolve()
    if default_path.exists():
        return default_path, False
    return None, False


def load_agent_registry(
    config_path: Path | None = None,
    base_registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
) -> AgentRegistry:
    path, explicit = discover_agent_config_path(config_path)
    if path is None:
        return base_registry
    if not path.exists():
        if explicit:
            raise AgentConfigError(f"Agent config file does not exist: {path}")
        return base_registry
    definitions = load_agent_definitions(path)
    return base_registry.merged_with(definitions)


def load_agent_definitions(config_path: Path) -> tuple[AgentDefinition, ...]:
    config_path = config_path.expanduser().resolve()
    secret_values: set[str] = set()
    try:
        raw = _load_yaml_mapping(config_path)
        _assert_fixed_top_level(raw, config_path)
        raw = _resolve_config_env(raw, secret_values)
        config = AgentConfigFile.model_validate(raw)
        _validate_unique("llms", [item.name for item in config.llms])
        _validate_unique("tools", [item.name for item in config.tools])
        _validate_unique("agents", [item.name for item in config.agents])
        return _build_agent_definitions(config, config_path, secret_values)
    except AgentConfigError:
        raise
    except ValidationError as exc:
        raise AgentConfigError(_mask_secrets(str(exc), secret_values)) from exc
    except Exception as exc:
        raise AgentConfigError(_mask_secrets(str(exc), secret_values)) from exc


def resolve_env_reference(value: str) -> str:
    match = _ENV_REF_RE.match(value)
    if not match:
        return value
    env_name, default = match.groups()
    if env_name in os.environ:
        return sanitize_text(os.environ[env_name])
    if default is not None:
        return sanitize_text(default)
    raise AgentConfigError(f"Environment variable '{env_name}' is not set")


def mask_secrets(message: str, values: Iterable[str] = ()) -> str:
    return _mask_secrets(message, set(values))


def _load_yaml_mapping(config_path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentConfigError(f"Agent config file does not exist: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise AgentConfigError(f"Invalid YAML in agent config {config_path}: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise AgentConfigError("Agent config must be a YAML mapping with llms, tools, and agents")
    return loaded


def _assert_fixed_top_level(raw: Mapping[str, Any], config_path: Path) -> None:
    expected = {"llms", "tools", "agents"}
    actual = set(raw)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise AgentConfigError(
            f"Agent config {config_path} is missing top-level sections: {', '.join(missing)}"
        )
    if extra:
        raise AgentConfigError(
            f"Agent config {config_path} has unknown top-level sections: {', '.join(extra)}"
        )


def _resolve_config_env(raw: Any, secret_values: set[str], key_path: tuple[str, ...] = ()) -> Any:
    if isinstance(raw, dict):
        return {
            key: _resolve_config_env(value, secret_values, (*key_path, str(key)))
            for key, value in raw.items()
        }
    if isinstance(raw, list):
        return [_resolve_config_env(value, secret_values, key_path) for value in raw]
    if isinstance(raw, str) and _is_env_resolvable_path(key_path):
        resolved = resolve_env_reference(raw)
        if _is_secret_path(key_path):
            secret_values.add(resolved)
        return resolved
    if isinstance(raw, str) and _is_secret_path(key_path):
        secret_values.add(raw)
    return raw


def _is_env_resolvable_path(key_path: tuple[str, ...]) -> bool:
    if not key_path:
        return False
    if len(key_path) >= 3 and key_path[0] == "tools" and "config" in key_path:
        return True
    return key_path[-1] in {"model", "api_key", "base_url"}


def _is_secret_path(key_path: tuple[str, ...]) -> bool:
    return any(any(token in part.lower() for token in _SECRET_KEYS) for part in key_path)


def _validate_unique(section: str, names: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        key = name.strip()
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    if duplicates:
        raise AgentConfigError(
            f"Duplicate names in {section}: {', '.join(sorted(duplicates))}"
        )


def _build_agent_definitions(
    config: AgentConfigFile,
    config_path: Path,
    secret_values: set[str],
) -> tuple[AgentDefinition, ...]:
    llms = {item.name: item for item in config.llms}
    tools = {item.name: item for item in config.tools}
    agents = {item.name: item for item in config.agents}
    _validate_references(llms, tools, agents)
    _validate_subagent_cycles(agents)
    tool_providers = {
        name: _instantiate_tool_provider(item, secret_values) for name, item in tools.items()
    }
    return tuple(
        _to_agent_definition(agent, llms, tool_providers, config_path)
        for agent in config.agents
    )


def _validate_references(
    llms: Mapping[str, LlmResourceConfig],
    tools: Mapping[str, ToolResourceConfig],
    agents: Mapping[str, AgentResourceConfig],
) -> None:
    for agent in agents.values():
        if agent.llm and agent.llm not in llms:
            raise AgentConfigError(f"Agent '{agent.name}' references unknown LLM '{agent.llm}'")
        for tool_name in agent.tools:
            if tool_name not in tools:
                raise AgentConfigError(
                    f"Agent '{agent.name}' references unknown tool '{tool_name}'"
                )
        for subagent_name in agent.subagents:
            if subagent_name not in agents:
                raise AgentConfigError(
                    f"Agent '{agent.name}' references unknown subagent '{subagent_name}'"
                )


def _validate_subagent_cycles(agents: Mapping[str, AgentResourceConfig]) -> None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            cycle = [*visiting[visiting.index(name) :], name]
            raise AgentConfigError(f"SubAgent cycle detected: {' -> '.join(cycle)}")
        visiting.append(name)
        for child in agents[name].subagents:
            visit(child)
        visiting.pop()
        visited.add(name)

    for name in agents:
        visit(name)


def _instantiate_tool_provider(
    item: ToolResourceConfig,
    secret_values: set[str],
) -> AgentToolProvider:
    try:
        module_name, _, class_name = item.provider.rpartition(".")
        if not module_name or not class_name:
            raise AgentConfigError(
                f"Tool '{item.name}' provider must be a fully qualified class path"
            )
        module = importlib.import_module(module_name)
        provider_cls = getattr(module, class_name)
        provider = provider_cls(**item.config)
        if not hasattr(provider, "tools_for_thread"):
            raise AgentConfigError(
                f"Tool '{item.name}' provider does not implement tools_for_thread(thread_id)"
            )
        return provider
    except AgentConfigError:
        raise
    except Exception as exc:
        raise AgentConfigError(
            _mask_secrets(f"Failed to initialize tool '{item.name}': {exc}", secret_values)
        ) from exc


def _to_agent_definition(
    agent: AgentResourceConfig,
    llms: Mapping[str, LlmResourceConfig],
    tool_providers: Mapping[str, AgentToolProvider],
    config_path: Path,
) -> AgentDefinition:
    llm = _to_llm_resource(llms[agent.llm]) if agent.llm else None
    return AgentDefinition(
        name=agent.name,
        system_prompt=_resolve_system_prompt(agent, config_path),
        llm=llm,
        skills=_to_toggle(agent.skills, config_path),
        memory=_to_toggle(agent.memory, config_path),
        include_builtin_tools=agent.include_builtin_tools,
        tool_providers=tuple(tool_providers[name] for name in agent.tools),
        subagent_names=tuple(agent.subagents),
        create_kwargs=dict(agent.create_kwargs),
    )


def _to_llm_resource(item: LlmResourceConfig) -> LlmResource:
    return LlmResource(
        name=item.name,
        model=item.model,
        api_key=item.api_key,
        base_url=item.base_url,
        kwargs=dict(item.kwargs),
    )


def _resolve_system_prompt(agent: AgentResourceConfig, config_path: Path) -> str:
    if agent.system_prompt_file is not None:
        path = _resolve_config_path(agent.system_prompt_file, config_path)
        try:
            return sanitize_text(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AgentConfigError(
                f"Agent '{agent.name}' system_prompt_file does not exist: {path}"
            ) from exc
    if agent.system_prompt is not None:
        return sanitize_text(agent.system_prompt)
    return DEFAULT_SYSTEM_PROMPT


def _to_toggle(value: bool | ToggleConfig, config_path: Path) -> AgentResourceToggle:
    if isinstance(value, bool):
        return AgentResourceToggle(enabled=value)
    return AgentResourceToggle(
        enabled=value.enabled,
        paths=tuple(_resolve_config_path(path, config_path) for path in value.paths),
    )


def _resolve_config_path(path: Path, config_path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (config_path.parent / expanded).resolve()


def _mask_secrets(message: str, values: set[str]) -> str:
    masked = sanitize_text(message)
    for value in sorted(values, key=len, reverse=True):
        if value:
            masked = masked.replace(value, "***")
    masked = _mask_url_credentials(masked)
    return masked


def _mask_url_credentials(message: str) -> str:
    parts = message.split()
    masked_parts: list[str] = []
    for part in parts:
        if "://" not in part or "@" not in part:
            masked_parts.append(part)
            continue
        try:
            parsed = urlsplit(part)
        except ValueError:
            masked_parts.append(part)
            continue
        if "@" not in parsed.netloc:
            masked_parts.append(part)
            continue
        userinfo, _, hostinfo = parsed.netloc.rpartition("@")
        if ":" in userinfo:
            user, _, _ = userinfo.partition(":")
            netloc = f"{user}:***@{hostinfo}"
        else:
            netloc = f"***@{hostinfo}"
        masked_parts.append(urlunsplit(parsed._replace(netloc=netloc)))
    return " ".join(masked_parts)


def prepare_external_path_in_session(
    source: Path,
    session_dir: Path,
    category: str,
) -> Path:
    """Mirror a configured read-only source into a session-owned directory."""

    source = source.expanduser().resolve()
    target_root = session_dir / ".configured" / category / _path_token(source)
    if source.is_dir():
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(source, target_root)
        return target_root
    if source.is_file():
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / source.name
        shutil.copy2(source, target)
        return target
    raise AgentConfigError(f"Configured {category} path does not exist: {source}")


def _path_token(path: Path) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.as_posix()).strip("._-")
    return sanitized[-80:] or "path"
