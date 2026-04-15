from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from agents.config import Settings
from agents.core.definitions import (
    DEFAULT_AGENT_REGISTRY,
    DEFAULT_SYSTEM_PROMPT,
    AgentDefinition,
    AgentRegistry,
    LlmResource,
    prepare_external_path_in_session,
)
from agents.core.tools import AgentToolProvider, collect_tools


class AgentRuntime:
    """Creates DeepAgents runtimes while keeping app concerns outside the engine."""

    def __init__(
        self,
        settings: Settings,
        definition: AgentDefinition,
        registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
        tool_providers: Iterable[AgentToolProvider] = (),
    ) -> None:
        self.settings = settings
        self.definition = definition
        self.registry = registry
        self.tool_providers = tuple(tool_providers)

    def build(self, thread_id: str) -> Any:
        return build_agent(
            self.settings,
            thread_id=thread_id,
            definition=self.definition,
            registry=self.registry,
            tools=collect_tools(thread_id, self.tool_providers),
        )


def _to_backend_absolute(path: Path, session_dir: Path) -> str:
    relative = path.resolve().relative_to(session_dir.resolve())
    return f"/{relative.as_posix()}"


def _collect_memory_files(
    settings: Settings,
    thread_id: str,
    session_dir: Path,
    definition: AgentDefinition,
) -> list[str]:
    memory_dir = settings.effective_session_memory_dir(thread_id)
    files: list[str] = []
    if memory_dir.exists():
        for path in sorted(memory_dir.rglob("*.md")):
            files.append(_to_backend_absolute(path, session_dir))
    for source in definition.memory.paths:
        mirrored = prepare_external_path_in_session(source, session_dir, "memory")
        if mirrored.is_dir():
            for path in sorted(mirrored.rglob("*.md")):
                files.append(_to_backend_absolute(path, session_dir))
        else:
            files.append(_to_backend_absolute(mirrored, session_dir))
    return files


def _collect_skill_roots(
    settings: Settings,
    thread_id: str,
    session_dir: Path,
    definition: AgentDefinition,
) -> list[str]:
    skills_dir = settings.effective_session_skills_dir(thread_id)
    roots: list[str] = []
    if skills_dir.exists():
        roots.append(_to_backend_absolute(skills_dir, session_dir))
    for source in definition.skills.paths:
        mirrored = prepare_external_path_in_session(source, session_dir, "skills")
        root = mirrored if mirrored.is_dir() else mirrored.parent
        roots.append(_to_backend_absolute(root, session_dir))
    return roots


def _openai_model_name(model: str) -> str:
    if model.startswith("openai:"):
        return model.removeprefix("openai:")
    return model


def build_chat_model(settings: Settings, llm: LlmResource | None = None) -> ChatOpenAI:
    model = llm.model if llm and llm.model else settings.model
    base_url = llm.base_url if llm and llm.base_url else settings.effective_openai_base_url
    api_key = llm.api_key if llm and llm.api_key else settings.openai_api_key
    extra_kwargs = dict(llm.kwargs) if llm else {}
    kwargs = {
        "model": _openai_model_name(model),
        "base_url": base_url,
        "use_responses_api": False,
        **extra_kwargs,
    }
    if api_key:
        kwargs["api_key"] = api_key
    return ChatOpenAI(**kwargs)


def build_agent(
    settings: Settings,
    thread_id: str,
    definition: AgentDefinition,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
    tools: Iterable[Any] = (),
):
    session_dir = settings.ensure_session_directories(thread_id)
    model = build_chat_model(settings, definition.llm)
    backend = FilesystemBackend(root_dir=str(session_dir), virtual_mode=True)
    tool_list = list(tools)

    kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": definition.system_prompt,
        "backend": backend,
        **definition.create_kwargs,
    }
    if definition.include_memory:
        kwargs["memory"] = _collect_memory_files(settings, thread_id, session_dir, definition)
    if definition.include_skills:
        kwargs["skills"] = _collect_skill_roots(settings, thread_id, session_dir, definition)
    if tool_list:
        kwargs["tools"] = tool_list
    if definition.subagent_names:
        kwargs["subagents"] = _build_subagent_specs(
            settings=settings,
            thread_id=thread_id,
            session_dir=session_dir,
            registry=registry,
            names=definition.subagent_names,
        )

    return create_deep_agent(**kwargs)


def _build_subagent_specs(
    settings: Settings,
    thread_id: str,
    session_dir: Path,
    registry: AgentRegistry,
    names: Iterable[str],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for name in names:
        definition = registry.get(name)
        spec: dict[str, Any] = {
            "name": definition.name,
            "description": f"Configured subagent '{definition.name}'.",
            "system_prompt": definition.system_prompt,
            "model": build_chat_model(settings, definition.llm),
        }
        tool_list = collect_tools(thread_id, definition.tool_providers)
        if tool_list:
            spec["tools"] = tool_list
        if definition.include_skills:
            spec["skills"] = _collect_skill_roots(settings, thread_id, session_dir, definition)
        specs.append(spec)
    return specs
