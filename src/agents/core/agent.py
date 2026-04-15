from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from agents.config import Settings
from agents.core.tools import AgentToolProvider, collect_tools

DEFAULT_SYSTEM_PROMPT = "你是我的个人 Agent。"


class AgentRuntime:
    """Creates DeepAgents runtimes while keeping app concerns outside the engine."""

    def __init__(
        self,
        settings: Settings,
        tool_providers: Iterable[AgentToolProvider] = (),
    ) -> None:
        self.settings = settings
        self.tool_providers = tuple(tool_providers)

    def build(self, thread_id: str) -> Any:
        return build_agent(
            self.settings,
            thread_id=thread_id,
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


def build_agent(settings: Settings, thread_id: str, tools: Iterable[Any] = ()):
    session_dir = settings.ensure_session_directories(thread_id)
    memory_files = _collect_memory_files(settings, thread_id, session_dir)
    skill_roots = _collect_skill_roots(settings, thread_id, session_dir)
    model = build_chat_model(settings)
    backend = FilesystemBackend(root_dir=str(session_dir), virtual_mode=True)
    tool_list = list(tools)

    kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "memory": memory_files,
        "skills": skill_roots,
        "backend": backend,
    }
    if tool_list:
        kwargs["tools"] = tool_list

    return create_deep_agent(**kwargs)
