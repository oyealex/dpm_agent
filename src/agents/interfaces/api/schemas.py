from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agents.domain.models import AgentEvent


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ChatResponse(BaseModel):
    thread_id: str
    reply: str


class AgentEventResponse(BaseModel):
    event_type: str
    role: str
    content: str
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_event(cls, event: AgentEvent) -> AgentEventResponse:
        return cls(
            event_type=event.event_type,
            role=event.role,
            content=event.content,
            metadata=event.metadata,
        )
