from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from agents.config import Settings
from agents.core.definitions import AgentConfigError, load_agent_registry


INSTALL_API_MESSAGE = (
    "API dependencies are required to run the API server. "
    'Install them with: pip install -e ".[api]"'
)


def build_parser(settings: Settings | None = None) -> argparse.ArgumentParser:
    settings = settings or Settings()
    parser = argparse.ArgumentParser(description="Agents API server")
    parser.add_argument(
        "--host",
        default=settings.api_host,
        help=f"Host interface to bind, defaults to {settings.api_host}.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.api_port,
        help=f"Port to bind, defaults to {settings.api_port}.",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=settings.api_reload,
        help=f"Reload the server when source files change, defaults to {settings.api_reload}.",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=settings.debug,
        help=f"Enable debug logging, defaults to {settings.debug}.",
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
        help="Path to agents.yaml. Defaults to ./agents.yaml when it exists.",
    )
    return parser


def main() -> None:
    settings = Settings()
    parser = build_parser(settings)
    args = parser.parse_args()

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

    uvicorn.run(
        create_app(agent_name=args.agent, agent_config_path=args.agent_config, agent_registry=registry),
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )
