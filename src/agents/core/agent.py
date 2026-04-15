from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from agents.config import Settings
from agents.core.tools import AgentToolProvider, collect_tools

DEFAULT_SYSTEM_PROMPT = "你是我的个人 Agent。"


@dataclass(frozen=True)
class AgentDefinition:
    """Declarative agent profile for pluggable multi-agent runtime bootstrapping."""

    name: str
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    include_memory: bool = True
    include_skills: bool = True
    include_builtin_tools: bool = True
    tool_providers: tuple[AgentToolProvider, ...] = ()
    subagents: tuple[Any, ...] = ()
    create_kwargs: dict[str, Any] = field(default_factory=dict)


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


class AgentRuntime:
    """Creates DeepAgents runtimes while keeping app concerns outside the engine."""

    def __init__(
        self,
        settings: Settings,
        definition: AgentDefinition,
        tool_providers: Iterable[AgentToolProvider] = (),
    ) -> None:
        self.settings = settings
        self.definition = definition
        self.tool_providers = tuple(tool_providers)

    def build(self, thread_id: str) -> Any:
        return build_agent(
            self.settings,
            thread_id=thread_id,
            definition=self.definition,
            tools=collect_tools(thread_id, self.tool_providers),
        )


def _to_backend_absolute(path: Path, session_dir: Path) -> str:
    relative = path.resolve().relative_to(session_dir.resolve())
    return f"/{relative.as_posix()}"


def _collect_memory_files(settings: Settings, thread_id: str, session_dir: Path) -> list[str]:
    memory_dir = settings.effective_session_memory_dir(thread_id)
    if not memory_dir.exists():
        return []
    files: list[str] = []
    for path in sorted(memory_dir.rglob("*.md")):
        files.append(_to_backend_absolute(path, session_dir))
    return files


def _collect_skill_roots(settings: Settings, thread_id: str, session_dir: Path) -> list[str]:
    skills_dir = settings.effective_session_skills_dir(thread_id)
    if not skills_dir.exists():
        return []
    return [_to_backend_absolute(skills_dir, session_dir)]


def _openai_model_name(model: str) -> str:
    if model.startswith("openai:"):
        return model.removeprefix("openai:")
    return model


def build_chat_model(settings: Settings) -> ChatOpenAI:
    kwargs = {
        "model": _openai_model_name(settings.model),
        "base_url": settings.effective_openai_base_url,
        "use_responses_api": False,
    }
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    return ChatOpenAI(**kwargs)


def build_agent(
    settings: Settings,
    thread_id: str,
    definition: AgentDefinition,
    tools: Iterable[Any] = (),
):
    session_dir = settings.ensure_session_directories(thread_id)
    model = build_chat_model(settings)
    backend = FilesystemBackend(root_dir=str(session_dir), virtual_mode=True)
    tool_list = list(tools)

    kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": definition.system_prompt,
        "backend": backend,
        **definition.create_kwargs,
    }
    if definition.include_memory:
        kwargs["memory"] = _collect_memory_files(settings, thread_id, session_dir)
    if definition.include_skills:
        kwargs["skills"] = _collect_skill_roots(settings, thread_id, session_dir)
    if tool_list:
        kwargs["tools"] = tool_list
    if definition.subagents:
        kwargs["subagents"] = list(definition.subagents)

    return create_deep_agent(**kwargs)
