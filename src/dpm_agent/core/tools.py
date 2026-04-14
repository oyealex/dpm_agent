from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


class AgentToolProvider(Protocol):
    """Supplies DeepAgents-compatible tools for an agent runtime."""

    def tools_for_thread(self, thread_id: str) -> Iterable[Any]:
        """Return tools enabled for one thread/session."""


class StaticToolProvider:
    """Small provider for app-level tools that are always enabled."""

    def __init__(self, tools: Iterable[Any] = ()) -> None:
        self._tools = tuple(tools)

    def tools_for_thread(self, thread_id: str) -> Iterable[Any]:
        return self._tools


def collect_tools(thread_id: str, providers: Iterable[AgentToolProvider]) -> list[Any]:
    tools: list[Any] = []
    for provider in providers:
        tools.extend(provider.tools_for_thread(thread_id))
    return tools
