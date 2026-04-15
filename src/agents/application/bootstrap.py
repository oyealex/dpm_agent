from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from threading import RLock

from agents.config import Settings
from agents.core.agent import AgentRuntime
from agents.core.service import AgentService
from agents.core.tools import AgentToolProvider
from agents.storage.db import connect_database, initialize_database
from agents.storage.repository import ChatRepository, MemoryRepository
from agents.tools import default_tool_providers

logger = logging.getLogger(__name__)


def build_service(
    sessions_dir: Path | None = None,
    tool_providers: Iterable[AgentToolProvider] = (),
    include_builtin_tools: bool = True,
) -> AgentService:
    settings = Settings(sessions_dir=sessions_dir) if sessions_dir else Settings()
    settings.ensure_directories()
    logger.info("Starting %s", settings.app_name)
    logger.info("Model setting: %s", settings.model)
    logger.info("Provider model name: %s", settings.effective_model_name)
    logger.info("OpenAI API mode: chat_completions")
    logger.info("OpenAI base URL: %s", settings.effective_openai_base_url)
    logger.info("OpenAI API key configured: %s", "yes" if settings.has_openai_api_key else "no")
    logger.info("Storage backend: %s", settings.effective_storage_backend)
    if settings.effective_storage_backend == "sqlite":
        logger.info("SQLite DB path: %s", settings.effective_db_path)
    logger.info("Sessions dir: %s", settings.effective_sessions_dir)
    logger.info(
        "Custom env loaded: total=%s agent=%s tool=%s",
        len(settings.effective_custom_env),
        len(settings.effective_custom_agent_env),
        len(settings.effective_custom_tool_env),
    )

    database = connect_database(settings)
    initialize_database(database)
    database_lock = RLock()

    providers = tuple(tool_providers)
    if include_builtin_tools:
        providers = (*default_tool_providers(), *providers)

    runtime = AgentRuntime(settings=settings, tool_providers=providers)
    return AgentService(
        settings=settings,
        chat_repository=ChatRepository(database, lock=database_lock),
        memory_repository=MemoryRepository(database, lock=database_lock),
        runtime=runtime,
    )
