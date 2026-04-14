from __future__ import annotations

import argparse
from pathlib import Path

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
