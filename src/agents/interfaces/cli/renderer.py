from __future__ import annotations

import os
import sys

from agents.domain.models import AgentEvent


COLORS = {
    "user": "\033[36m",
    "assistant": "\033[32m",
    "thinking": "\033[2m",
    "tool": "\033[33m",
    "system": "\033[35m",
    "error": "\033[31m",
    "reset": "\033[0m",
}


TOOL_CALL_PREVIEW_LIMIT = 500


def color(text: str, color_name: str) -> str:
    if not use_color():
        return text
    return f"{COLORS[color_name]}{text}{COLORS['reset']}"


def use_color() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def render_stream(events: object) -> None:
    assistant_open = False
    assistant_seen = False

    for event in events:
        if not isinstance(event, AgentEvent):
            continue
        if event.event_type == "user_message":
            continue
        if event.event_type == "assistant_delta":
            if not assistant_open:
                print(color("\nAgent> ", "assistant"), end="", flush=True)
                assistant_open = True
                assistant_seen = True
            print(color(event.content, "assistant"), end="", flush=True)
            continue

        if assistant_open:
            print()
            assistant_open = False

        if event.event_type == "assistant_message":
            if assistant_seen:
                continue
            prefix = _event_prefix(event)
            print(color(f"\n{prefix}Agent> {event.content}", "assistant"), flush=True)
            assistant_seen = True
        elif event.event_type == "thinking":
            prefix = _event_prefix(event)
            print(color(f"\n{prefix}Thinking> {event.content}", "thinking"), flush=True)
        elif event.event_type == "tool_call":
            prefix = _event_prefix(event)
            print(color(f"\n{prefix}Tool call> {_preview_tool_call(event.content)}", "tool"), flush=True)
        elif event.event_type == "tool_result":
            prefix = _event_prefix(event)
            print(color(f"\n{prefix}Tool result> {event.content}", "tool"), flush=True)
        elif event.event_type == "agent_step":
            print(color(f"\nEvent> {event.content}", "system"), flush=True)
        elif event.event_type == "internal_state":
            continue

    if assistant_open:
        print()


def _preview_tool_call(content: str) -> str:
    if len(content) <= TOOL_CALL_PREVIEW_LIMIT:
        return content
    remaining = len(content) - TOOL_CALL_PREVIEW_LIMIT
    return f"{content[:TOOL_CALL_PREVIEW_LIMIT]}... (remaining {remaining} chars)"


def _event_prefix(event: AgentEvent) -> str:
    subagent_name = _extract_subagent_name(event)
    if not subagent_name:
        return ""
    return f"SubAgent({subagent_name}) > "


def _extract_subagent_name(event: AgentEvent) -> str | None:
    metadata = event.metadata or {}
    node = metadata.get("node")
    if not isinstance(node, str):
        return None
    parts = [part.strip() for part in node.split("/") if part.strip()]
    if len(parts) < 2:
        return None
    return parts[0]
