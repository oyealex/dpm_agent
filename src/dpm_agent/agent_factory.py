from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from dpm_agent.config import Settings


def _collect_memory_files(settings: Settings, thread_id: str) -> list[str]:
    memory_dir = settings.effective_session_memory_dir(thread_id)
    if not memory_dir.exists():
        return []
    return [str(path) for path in sorted(memory_dir.rglob("*.md"))]


def _collect_skill_roots(settings: Settings, thread_id: str) -> list[str]:
    skills_dir = settings.effective_session_skills_dir(thread_id)
    if not skills_dir.exists():
        return []
    return [str(skills_dir)]


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


def build_agent(settings: Settings, thread_id: str):
    session_dir = settings.ensure_session_directories(thread_id)
    memory_files = _collect_memory_files(settings, thread_id)
    skill_roots = _collect_skill_roots(settings, thread_id)
    model = build_chat_model(settings)
    backend = FilesystemBackend(root_dir=str(session_dir), virtual_mode=True)

    return create_deep_agent(
        model=model,
        system_prompt=settings.system_prompt,
        memory=memory_files,
        skills=skill_roots,
        backend=backend,
    )
