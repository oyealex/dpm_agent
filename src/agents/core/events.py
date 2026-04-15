from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from agents.domain.models import AgentEvent
from agents.sanitize import sanitize_json_value, sanitize_metadata, sanitize_text


def events_from_stream_chunk(chunk: Any) -> Iterator[AgentEvent]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        mode, payload = chunk
        if mode == "messages":
            yield from _events_from_message_payload(payload)
            return
        if mode == "updates":
            yield from _events_from_update_payload(payload)
            return

    yield from _events_from_update_payload(chunk)


def dedupe_events(events: Iterator[AgentEvent]) -> Iterator[AgentEvent]:
    seen: set[tuple[Any, ...]] = set()
    for event in events:
        key = _event_dedupe_key(event)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        yield event


def extract_last_text(result: object) -> str:
    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            return extract_message_text(messages[-1])
    return str(result)


def extract_message_text(message: Any) -> str:
    if isinstance(message, dict):
        return _extract_content_text(message.get("content", ""))

    content = getattr(message, "content", None)
    if content is not None:
        return _extract_content_text(content)

    return str(message)


def _extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return sanitize_text(content)

    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    texts.append(text)
                elif item.get("type") == "text" and isinstance(item.get("content"), str):
                    texts.append(item["content"])
        return sanitize_text("\n".join(texts).strip())

    return sanitize_text(str(content))


def _events_from_message_payload(payload: Any) -> Iterator[AgentEvent]:
    message = payload[0] if isinstance(payload, tuple) and payload else payload
    message_type = _message_type_name(message)
    text = extract_message_text(message)

    if message_type.endswith("AIMessageChunk"):
        if text:
            yield AgentEvent(
                event_type="assistant_delta",
                role="assistant",
                content=text,
                persist=False,
            )
        return

    tool_calls = getattr(message, "tool_calls", None) or []
    for tool_call in tool_calls:
        if not _is_complete_tool_call(tool_call):
            continue
        yield AgentEvent(
            event_type="tool_call",
            role="tool",
            content=_tool_call_content(tool_call),
            metadata=_safe_metadata(tool_call),
        )

    if message_type.endswith("AIMessage") and text:
        yield AgentEvent(
            event_type="assistant_message",
            role="assistant",
            content=text,
        )
    elif message_type.endswith("ToolMessage"):
        yield AgentEvent(
            event_type="tool_result",
            role="tool",
            content=text,
            metadata={"tool_call_id": getattr(message, "tool_call_id", None)},
        )


def _events_from_update_payload(payload: Any) -> Iterator[AgentEvent]:
    if isinstance(payload, dict):
        for node_name, node_update in payload.items():
            messages = _extract_update_messages(node_update)
            if not messages:
                if _is_internal_state_update(node_name, node_update):
                    yield AgentEvent(
                        event_type="internal_state",
                        role="system",
                        content=f"{node_name} updated",
                        metadata=_safe_metadata(node_update),
                        persist=False,
                    )
                    continue
                yield AgentEvent(
                    event_type="agent_step",
                    role="system",
                    content=f"{node_name} updated",
                    metadata=_safe_metadata(node_update),
                )
                continue
            for message in messages:
                yield from _events_from_update_message(message, node_name)


def _events_from_update_message(message: Any, node_name: str) -> Iterator[AgentEvent]:
    message_type = _message_type_name(message)
    text = extract_message_text(message)
    metadata = {"node": node_name, "message_type": message_type}

    tool_calls = getattr(message, "tool_calls", None) or []
    for tool_call in tool_calls:
        if not _is_complete_tool_call(tool_call):
            continue
        yield AgentEvent(
            event_type="tool_call",
            role="tool",
            content=_tool_call_content(tool_call),
            metadata={**metadata, **_safe_metadata(tool_call)},
        )

    if message_type.endswith("ToolMessage"):
        yield AgentEvent(
            event_type="tool_result",
            role="tool",
            content=text,
            metadata={**metadata, "tool_call_id": getattr(message, "tool_call_id", None)},
        )
    elif message_type.endswith("AIMessage") and text:
        yield AgentEvent(
            event_type="assistant_message",
            role="assistant",
            content=text,
            metadata=metadata,
        )
    elif _is_reasoning_message(message_type) and text:
        yield AgentEvent(
            event_type="thinking",
            role="assistant",
            content=text,
            metadata=metadata,
        )
    elif text:
        yield AgentEvent(
            event_type="internal_state",
            role="system",
            content=text,
            metadata=metadata,
            persist=False,
        )


def _extract_update_messages(update: Any) -> list[Any]:
    if isinstance(update, dict):
        messages = update.get("messages")
        if _is_state_overwrite(messages):
            return []
        if isinstance(messages, list):
            return messages
        if messages is not None:
            return [messages]
    messages = getattr(update, "messages", None)
    if _is_state_overwrite(messages):
        return []
    if isinstance(messages, list):
        return messages
    if messages is not None:
        return [messages]
    return []


def _message_type_name(message: Any) -> str:
    return type(message).__name__


def _is_internal_state_update(node_name: str, update: Any) -> bool:
    if "Middleware." in node_name:
        return True
    if isinstance(update, dict):
        return any(_is_state_overwrite(value) for value in update.values())
    return _is_state_overwrite(update)


def _is_state_overwrite(value: Any) -> bool:
    return _message_type_name(value) == "Overwrite"


def _is_reasoning_message(message_type: str) -> bool:
    return "Reasoning" in message_type or "Thinking" in message_type


def _event_dedupe_key(event: AgentEvent) -> tuple[Any, ...] | None:
    metadata = event.metadata or {}
    if event.event_type == "tool_call":
        return (
            event.event_type,
            metadata.get("id") or metadata.get("tool_call_id"),
            metadata.get("name"),
            event.content,
        )
    if event.event_type == "tool_result":
        return (
            event.event_type,
            metadata.get("tool_call_id"),
            event.content,
        )
    if event.event_type in {"agent_step", "internal_state"}:
        return (event.event_type, event.content)
    return None


def _is_complete_tool_call(tool_call: Any) -> bool:
    name = _tool_call_name(tool_call)
    if not name or name == "tool_call":
        return False
    args = _tool_call_args(tool_call)
    return args is not None


def _tool_call_content(tool_call: Any) -> str:
    name = _tool_call_name(tool_call) or "tool"
    args = _tool_call_args(tool_call) or {}
    return sanitize_text(f"{name} {sanitize_json_value(args)}".strip())


def _tool_call_name(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        name = tool_call.get("name") or tool_call.get("type")
    else:
        name = getattr(tool_call, "name", None) or getattr(tool_call, "type", None)
    return sanitize_text(str(name)) if name else None


def _tool_call_args(tool_call: Any) -> Any:
    if isinstance(tool_call, dict):
        return tool_call.get("args") if "args" in tool_call else tool_call.get("arguments")
    if hasattr(tool_call, "args"):
        return getattr(tool_call, "args")
    return getattr(tool_call, "arguments", None)


def _safe_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return sanitize_metadata({str(key): _safe_json_value(item) for key, item in value.items()})
    return {}


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return sanitize_json_value(value)
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return sanitize_metadata({str(key): _safe_json_value(item) for key, item in value.items()})
    return sanitize_text(str(value))
