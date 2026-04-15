from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from agents.config import Settings
from agents.core.agent import AgentRuntime
from agents.core.definitions import AgentEventContentLimits
from agents.core.events import dedupe_events, events_from_stream_chunk, extract_last_text
from agents.domain.models import AgentEvent, ChatResult
from agents.sanitize import sanitize_text
from agents.storage.repository import ChatRepository, MemoryRepository

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(
        self,
        settings: Settings,
        chat_repository: ChatRepository,
        memory_repository: MemoryRepository,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.chat_repository = chat_repository
        self.memory_repository = memory_repository
        self.runtime = runtime or AgentRuntime(settings)
        self._agents: dict[tuple[str, str], Any] = {}

    def chat(self, thread_id: str, message: str, user_id: str | None = None) -> ChatResult:
        user_id = self.settings.normalize_user_id(user_id)
        thread_id = self.settings.normalize_thread_id(thread_id)
        events = list(self.chat_stream(thread_id=thread_id, message=message, user_id=user_id))
        reply = "".join(
            event.content for event in events if event.event_type == "assistant_delta"
        ).strip()
        if not reply:
            reply = _last_event_content(events, "assistant_message")
        return ChatResult(user_id=user_id, thread_id=thread_id, reply=reply, events=events)

    def chat_stream(
        self,
        thread_id: str,
        message: str,
        user_id: str | None = None,
    ) -> Iterator[AgentEvent]:
        user_id = self.settings.normalize_user_id(user_id)
        thread_id = self.settings.normalize_thread_id(thread_id)
        message = sanitize_text(message)
        logger.info("Preparing chat request: user_id=%s thread_id=%s", user_id, thread_id)
        self.settings.ensure_session_directories(user_id, thread_id)
        self.memory_repository.sync_directory(
            self.settings.effective_session_memory_dir(user_id, thread_id)
        )
        self.chat_repository.ensure_thread(thread_id=thread_id, title=thread_id, user_id=user_id)
        history = self.chat_repository.list_messages(thread_id, user_id=user_id)
        logger.info("Loaded %d historical messages", len(history))

        messages = [
            {"role": sanitize_text(item.role), "content": sanitize_text(item.content)}
            for item in history
        ]
        messages.append({"role": "user", "content": message})

        logger.info(
            "Invoking agent: model=%s base_url=%s api_mode=chat_completions message_count=%d session_dir=%s",
            self.settings.effective_model_name,
            self.settings.effective_openai_base_url,
            len(messages),
            self.settings.effective_session_dir(user_id, thread_id),
        )
        events: list[AgentEvent] = [
            AgentEvent(event_type="user_message", role="user", content=message)
        ]
        yield events[0]

        reply_parts: list[str] = []
        try:
            for event in dedupe_events(
                self._stream_agent(messages=messages, user_id=user_id, thread_id=thread_id)
            ):
                event = apply_event_content_limits(
                    event,
                    self.runtime.definition.event_content_limits,
                )
                if event.event_type == "assistant_delta":
                    reply_parts.append(event.content)
                events.append(event)
                yield event
        except Exception:
            logger.exception("Agent invocation failed")
            raise

        reply = "".join(reply_parts).strip()
        if not reply:
            reply = _last_event_content(events, "assistant_message")
        logger.info("Agent replied with %d characters", len(reply))

        if reply and not any(event.event_type == "assistant_message" for event in events):
            assistant_event = AgentEvent(
                event_type="assistant_message",
                role="assistant",
                content=reply,
            )
            events.append(assistant_event)
            yield assistant_event

        self.chat_repository.add_events(thread_id, events, user_id=user_id)

    def _stream_agent(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        thread_id: str,
    ) -> Iterator[AgentEvent]:
        payload = {"messages": messages}
        runtime_thread_id = self.settings.runtime_thread_id(user_id, thread_id)
        config = {"configurable": {"thread_id": runtime_thread_id}}
        agent = self._get_agent(user_id, thread_id)
        try:
            stream = agent.stream(payload, config=config, stream_mode=["messages", "updates"])
        except TypeError:
            result = agent.invoke(payload, config=config)
            yield AgentEvent(
                event_type="assistant_message",
                role="assistant",
                content=extract_last_text(result),
            )
            return

        for chunk in stream:
            yield from events_from_stream_chunk(chunk)

    def _get_agent(self, user_id: str, thread_id: str) -> Any:
        key = (user_id, thread_id)
        agent = self._agents.get(key)
        if agent is None:
            agent = self.runtime.build(user_id, thread_id)
            self._agents[key] = agent
        return agent


def _last_event_content(events: list[AgentEvent], event_type: str) -> str:
    for event in reversed(events):
        if event.event_type == event_type:
            return event.content.strip()
    return ""


def apply_event_content_limits(
    event: AgentEvent,
    limits: AgentEventContentLimits,
) -> AgentEvent:
    limit = limits.limit_for(event.event_type)
    if limit is None or len(event.content) <= limit:
        return event

    content, omitted = _truncate_with_omission(event.content, limit)
    metadata = dict(event.metadata or {})
    metadata.update(
        {
            "content_truncated": True,
            "original_content_length": len(event.content),
            "omitted_content_chars": omitted,
        }
    )
    return AgentEvent(
        event_type=event.event_type,
        role=event.role,
        content=content,
        metadata=metadata,
        persist=event.persist,
    )


def _truncate_with_omission(content: str, max_chars: int) -> tuple[str, int]:
    if max_chars < 1 or len(content) <= max_chars:
        return content, 0

    suffix_template = "... (remaining {remaining} chars)"
    omitted = len(content) - max_chars
    while True:
        suffix = suffix_template.format(remaining=omitted)
        prefix_length = max_chars - len(suffix)
        if prefix_length <= 0:
            compact_suffix = f"...(+{len(content)} chars)"
            return compact_suffix[:max_chars], len(content)
        next_omitted = len(content) - prefix_length
        if next_omitted == omitted:
            break
        omitted = next_omitted
    return f"{content[:prefix_length]}{suffix}", omitted
