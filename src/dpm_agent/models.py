from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dpm_agent.sanitize import sanitize_metadata, sanitize_text


@dataclass(slots=True)
class Message:
    role: str
    content: str
    message_type: str = "message"
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.role = sanitize_text(self.role)
        self.content = sanitize_text(self.content)
        self.message_type = sanitize_text(self.message_type)
        self.metadata = sanitize_metadata(self.metadata)


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
    thread_id: str
    reply: str
    events: list[AgentEvent]
