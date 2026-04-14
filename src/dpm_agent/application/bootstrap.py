from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from threading import RLock

from dpm_agent.config import Settings
from dpm_agent.core.agent import AgentRuntime
from dpm_agent.core.service import AgentService
from dpm_agent.core.tools import AgentToolProvider
from dpm_agent.storage.db import connect, initialize_database
from dpm_agent.storage.repository import ChatRepository, MemoryRepository
from dpm_agent.tools import default_tool_providers

logger = logging.getLogger(__name__)


def build_service(
    sessions_dir: Path | None = None,
    tool_providers: Iterable[AgentToolProvider] = (),
    include_builtin_tools: bool = True,
) -> AgentService:
    settings = Settings(sessions_dir=sessions_dir) if sessions_dir else Settings()
    settings.ensure_directories()
    settings.apply_provider_environment()
    logger.info("Starting %s", settings.app_name)
    logger.info("Model setting: %s", settings.model)
    logger.info("Provider model name: %s", settings.effective_model_name)
    logger.info("OpenAI API mode: chat_completions")
    logger.info("OpenAI base URL: %s", settings.effective_openai_base_url)
    logger.info("OpenAI API key configured: %s", "yes" if settings.has_openai_api_key else "no")
    logger.info("SQLite DB path: %s", settings.effective_db_path)
    logger.info("Sessions dir: %s", settings.effective_sessions_dir)

    connection = connect(settings.effective_db_path)
    initialize_database(connection)
    database_lock = RLock()

    providers = tuple(tool_providers)
    if include_builtin_tools:
        providers = (*default_tool_providers(), *providers)

    runtime = AgentRuntime(settings=settings, tool_providers=providers)
    return AgentService(
        settings=settings,
        chat_repository=ChatRepository(connection, lock=database_lock),
        memory_repository=MemoryRepository(connection, lock=database_lock),
        runtime=runtime,
    )
