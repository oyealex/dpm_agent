from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agents.domain.models import AgentEvent, Message, ThreadSummary


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    user_id: str
    thread_id: str
    reply: str


class ThreadSummaryResponse(BaseModel):
    user_id: str
    thread_id: str
    title: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_summary(cls, summary: ThreadSummary) -> ThreadSummaryResponse:
        return cls(
            user_id=summary.user_id,
            thread_id=summary.thread_id,
            title=summary.title,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


class ChatListResponse(BaseModel):
    user_id: str
    items: list[ThreadSummaryResponse]
    limit: int
    offset: int
    has_more: bool


class MessageResponse(BaseModel):
    role: str
    message_type: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str | None = None

    @classmethod
    def from_message(cls, message: Message) -> MessageResponse:
        return cls(
            role=message.role,
            message_type=message.message_type,
            content=message.content,
            metadata=message.metadata,
            created_at=message.created_at,
        )


class ChatHistoryResponse(BaseModel):
    user_id: str
    thread_id: str
    items: list[MessageResponse]
    limit: int
    offset: int
    has_more: bool


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
