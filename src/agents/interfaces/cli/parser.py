from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_THREAD_ID = "default"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agents CLI")
    parser.set_defaults(command="chat", thread_id=DEFAULT_THREAD_ID, message=None, agent_name="default")
    parser.add_argument(
        "agent_name",
        nargs="?",
        default="default",
        help="Agent profile name, defaults to 'default'.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("chat",),
        default="chat",
        help="Command to run. Defaults to chat.",
    )
    parser.add_argument(
        "--thread-id",
        default=DEFAULT_THREAD_ID,
        help=f"Conversation thread ID, defaults to '{DEFAULT_THREAD_ID}'",
    )
    parser.add_argument(
        "--message",
        help="Send one message and exit. If omitted, starts interactive mode.",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Directory for per-session files, skills, and memory. Defaults to ./data/sessions.",
    )
    parser.add_argument(
        "--agent-config",
        type=Path,
        default=None,
        help="Path to agents.yaml. Defaults to ./agents.yaml when it exists.",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a new session with a random thread ID.",
    )

    return parser
