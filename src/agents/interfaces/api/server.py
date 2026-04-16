from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from agents.config import Settings, SettingsError
from agents.core.definitions import AgentConfigError, load_agent_registry
from agents.runtime_encoding import enforce_utf8_runtime


INSTALL_API_MESSAGE = (
    "API dependencies are required to run the API server. "
    'Install them with: pip install -e ".[api]"'
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agents API server")
    parser.add_argument(
        "--host",
        default=None,
        help="Host interface to bind. Defaults to value from agents.yaml settings.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind. Defaults to value from agents.yaml settings.",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Reload the server when source files change. Defaults to value from agents.yaml settings.",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable debug logging. Defaults to value from agents.yaml settings.",
    )
    parser.add_argument(
        "--agent",
        default="default",
        help="Agent profile to serve, defaults to 'default'.",
    )
    parser.add_argument(
        "--agent-config",
        type=Path,
        default=None,
        help="Path to agents.yaml (includes settings + agent registry). Defaults to ./agents.yaml.",
    )
    return parser


def main() -> None:
    enforce_utf8_runtime()
    parser = build_parser()
    args = parser.parse_args()
    try:
        settings = Settings.load(args.agent_config)
    except SettingsError as exc:
        raise SystemExit(str(exc)) from exc

    if importlib.util.find_spec("fastapi") is None:
        raise SystemExit(INSTALL_API_MESSAGE)

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(INSTALL_API_MESSAGE) from exc

    try:
        registry = load_agent_registry(args.agent_config)
    except AgentConfigError as exc:
        raise SystemExit(str(exc)) from exc

    if args.agent not in registry.list_names():
        options = ", ".join(registry.list_names())
        raise SystemExit(f"Unknown agent '{args.agent}'. Available: {options}")

    from agents.interfaces.api.app import create_app

    host = settings.api_host if args.host is None else args.host
    port = settings.api_port if args.port is None else args.port
    reload = settings.api_reload if args.reload is None else args.reload
    debug = settings.debug if args.debug is None else args.debug

    uvicorn.run(
        create_app(
            agent_name=args.agent,
            agent_config_path=args.agent_config,
            agent_registry=registry,
        ),
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if debug else "info",
    )
