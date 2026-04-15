from __future__ import annotations

import argparse
import sys
import uuid

from agents.config import Settings
from agents.core.service import AgentService
from agents.interfaces.cli.parser import build_parser
from agents.interfaces.cli.renderer import color, render_stream
from agents.logging import configure_logging, set_logging_verbose
from agents.application.bootstrap import build_service
from agents.core.definitions import AgentConfigError, load_agent_registry
from agents.sanitize import sanitize_text


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _normalize_args(args)
    settings = Settings()
    configure_logging(verbose=settings.debug if args.debug is None else args.debug)
    registry = _load_registry(args.agent_config)
    _validate_agent_name(args.agent_name, registry.list_names())

    if args.command == "chat":
        thread_id = _resolve_thread_id(args)
        service = build_service(
            sessions_dir=args.sessions_dir,
            agent_config_path=args.agent_config,
            agent_registry=registry,
            agent_name=args.agent_name,
        )
        if args.message:
            args.message = sanitize_text(args.message)
            print(color(f"You> {args.message}", "user"))
            render_stream(service.chat_stream(thread_id=thread_id, message=args.message))
            return

        run_interactive_chat(service=service, thread_id=thread_id, agent_name=args.agent_name)




def _load_registry(agent_config_path):
    try:
        return load_agent_registry(agent_config_path)
    except AgentConfigError as exc:
        raise SystemExit(str(exc)) from exc


def _validate_agent_name(agent_name: str, available: tuple[str, ...]) -> None:
    if agent_name not in available:
        options = ", ".join(available)
        raise SystemExit(f"Unknown agent '{agent_name}'. Available: {options}")


def _normalize_args(args: argparse.Namespace) -> None:
    if args.agent_name == "chat" and args.command == "chat":
        args.agent_name = "default"


def _resolve_thread_id(args: argparse.Namespace) -> str:
    if args.new:
        return f"session-{uuid.uuid4().hex}"
    return sanitize_text(args.thread_id)


def run_interactive_chat(service: AgentService, thread_id: str, agent_name: str = "default") -> None:
    print(f"Agents interactive chat started. agent={agent_name} thread_id={thread_id}")
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
