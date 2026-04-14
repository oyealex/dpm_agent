from __future__ import annotations

import os
import sys

from dpm_agent.domain.models import AgentEvent


COLORS = {
    "user": "\033[36m",
    "assistant": "\033[32m",
    "thinking": "\033[2m",
    "tool": "\033[33m",
    "system": "\033[35m",
    "error": "\033[31m",
    "reset": "\033[0m",
}


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
            print(color(f"\nAgent> {event.content}", "assistant"), flush=True)
            assistant_seen = True
        elif event.event_type == "thinking":
            print(color(f"\nThinking> {event.content}", "thinking"), flush=True)
        elif event.event_type == "tool_call":
            print(color(f"\nTool call> {event.content}", "tool"), flush=True)
        elif event.event_type == "tool_result":
            print(color(f"\nTool result> {event.content}", "tool"), flush=True)
        elif event.event_type == "agent_step":
            print(color(f"\nEvent> {event.content}", "system"), flush=True)
        elif event.event_type == "internal_state":
            continue

    if assistant_open:
        print()
