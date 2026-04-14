from __future__ import annotations

import argparse
import sys
import uuid

from dpm_agent.core.service import AgentService
from dpm_agent.interfaces.cli.parser import build_parser
from dpm_agent.interfaces.cli.renderer import color, render_stream
from dpm_agent.logging import configure_logging, set_logging_verbose
from dpm_agent.application.bootstrap import build_service
from dpm_agent.sanitize import sanitize_text


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.debug)

    if args.command in {None, "chat"}:
        thread_id = _resolve_thread_id(args)
        service = build_service(sessions_dir=args.sessions_dir)
        if args.message:
            args.message = sanitize_text(args.message)
            print(color(f"You> {args.message}", "user"))
            render_stream(service.chat_stream(thread_id=thread_id, message=args.message))
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
            message = sanitize_text(input(color("\nYou> ", "user")).strip())
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
            render_stream(service.chat_stream(thread_id=thread_id, message=message))
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)
            continue


if __name__ == "__main__":
    main()
