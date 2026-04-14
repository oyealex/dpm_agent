from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import uuid

from dpm_agent.bootstrap import build_service
from dpm_agent.logging import configure_logging, set_logging_verbose
from dpm_agent.models import AgentEvent
from dpm_agent.sanitize import sanitize_text
from dpm_agent.service import AgentService

DEFAULT_THREAD_ID = "default"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DPM Agent CLI")
    parser.set_defaults(command=None, thread_id=DEFAULT_THREAD_ID, message=None)
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Directory for per-session files, skills, and memory. Defaults to ./data/sessions.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a new session with a random thread ID.",
    )
    subparsers = parser.add_subparsers(dest="command")

    chat_parser = subparsers.add_parser("chat", help="Start a continuous chat session")
    chat_parser.add_argument(
        "--thread-id",
        default=DEFAULT_THREAD_ID,
        help=f"Conversation thread ID, defaults to '{DEFAULT_THREAD_ID}'",
    )
    chat_parser.add_argument(
        "--message",
        help="Send one message and exit. If omitted, starts interactive mode.",
    )
    chat_parser.add_argument(
        "--new",
        action="store_true",
        help="Start a new session with a random thread ID.",
    )
    chat_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    chat_parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Directory for per-session files, skills, and memory. Defaults to ./data/sessions.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.debug)

    if args.command in {None, "chat"}:
        thread_id = _resolve_thread_id(args)
        service = build_service(sessions_dir=args.sessions_dir)
        if args.message:
            args.message = sanitize_text(args.message)
            print(_color(f"You> {args.message}", "user"))
            _render_stream(service.chat_stream(thread_id=thread_id, message=args.message))
            return

        run_interactive_chat(service=service, thread_id=thread_id)


def _resolve_thread_id(args: argparse.Namespace) -> str:
    if args.new:
        return f"session-{uuid.uuid4().hex}"
    return sanitize_text(args.thread_id)


def run_interactive_chat(service: AgentService, thread_id: str) -> None:
    print(f"DPM Agent interactive chat started. thread_id={thread_id}")
    print(f"Sessions dir: {service.settings.effective_sessions_dir}")
    print(f"Session dir: {service.settings.effective_session_dir(thread_id)}")
    print(f"Session skills: {service.settings.effective_session_skills_dir(thread_id)}")
    print(f"Session memory: {service.settings.effective_session_memory_dir(thread_id)}")
    print("Type /exit or /quit to leave. Type /help for commands.")

    while True:
        try:
            message = sanitize_text(input(_color("\nYou> ", "user")).strip())
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not message:
            continue
        if message in {"/exit", "/quit"}:
            print("Bye.")
            return
        if message == "/help":
            print("Commands: /help, /debug on, /debug off, /exit, /quit")
            continue
        if message == "/debug":
            print("Usage: /debug on | /debug off")
            continue
        if message == "/debug on":
            set_logging_verbose(True)
            print("Debug logging enabled.")
            continue
        if message == "/debug off":
            set_logging_verbose(False)
            print("Debug logging disabled.")
            continue

        try:
            _render_stream(service.chat_stream(thread_id=thread_id, message=message))
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)
            continue


COLORS = {
    "user": "\033[36m",
    "assistant": "\033[32m",
    "thinking": "\033[2m",
    "tool": "\033[33m",
    "system": "\033[35m",
    "error": "\033[31m",
    "reset": "\033[0m",
}


def _use_color() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _color(text: str, color_name: str) -> str:
    if not _use_color():
        return text
    return f"{COLORS[color_name]}{text}{COLORS['reset']}"


def _render_stream(events: object) -> None:
    assistant_open = False
    assistant_seen = False

    for event in events:
        if not isinstance(event, AgentEvent):
            continue
        if event.event_type == "user_message":
            continue
        if event.event_type == "assistant_delta":
            if not assistant_open:
                print(_color("\nAgent> ", "assistant"), end="", flush=True)
                assistant_open = True
                assistant_seen = True
            print(_color(event.content, "assistant"), end="", flush=True)
            continue

        if assistant_open:
            print()
            assistant_open = False

        if event.event_type == "assistant_message":
            if assistant_seen:
                continue
            print(_color(f"\nAgent> {event.content}", "assistant"), flush=True)
            assistant_seen = True
        elif event.event_type == "thinking":
            print(_color(f"\nThinking> {event.content}", "thinking"), flush=True)
        elif event.event_type == "tool_call":
            print(_color(f"\nTool call> {event.content}", "tool"), flush=True)
        elif event.event_type == "tool_result":
            print(_color(f"\nTool result> {event.content}", "tool"), flush=True)
        elif event.event_type == "agent_step":
            print(_color(f"\nEvent> {event.content}", "system"), flush=True)
        elif event.event_type == "internal_state":
            continue

    if assistant_open:
        print()


if __name__ == "__main__":
    main()
