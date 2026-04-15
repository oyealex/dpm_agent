from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.sanitize import sanitize_metadata, sanitize_text


@dataclass(slots=True)
class Message:
    role: str
    content: str
    message_type: str = "message"
    metadata: dict[str, Any] | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        self.role = sanitize_text(self.role)
        self.content = sanitize_text(self.content)
        self.message_type = sanitize_text(self.message_type)
        self.metadata = sanitize_metadata(self.metadata)
        self.created_at = sanitize_text(self.created_at) if self.created_at is not None else None


@dataclass(slots=True)
class AgentEvent:
    event_type: str
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    persist: bool = True

    def __post_init__(self) -> None:
        self.event_type = sanitize_text(self.event_type)
        self.role = sanitize_text(self.role)
        self.content = sanitize_text(self.content)
        self.metadata = sanitize_metadata(self.metadata)


@dataclass(slots=True)
class ChatResult:
    user_id: str
    thread_id: str
    reply: str
    events: list[AgentEvent]

    def __post_init__(self) -> None:
        self.user_id = sanitize_text(self.user_id)
        self.thread_id = sanitize_text(self.thread_id)
        self.reply = sanitize_text(self.reply)


@dataclass(slots=True)
class ThreadSummary:
    user_id: str
    thread_id: str
    title: str | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        self.user_id = sanitize_text(self.user_id)
        self.thread_id = sanitize_text(self.thread_id)
        self.title = sanitize_text(self.title) if self.title is not None else None
        self.created_at = sanitize_text(self.created_at)
        self.updated_at = sanitize_text(self.updated_at)


@dataclass(slots=True)
class Page:
    items: list[Any]
    limit: int
    offset: int
    has_more: bool
