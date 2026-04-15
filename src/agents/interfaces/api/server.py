from __future__ import annotations

import argparse
import importlib.util

from agents.config import Settings


INSTALL_API_MESSAGE = (
    "API dependencies are required to run the API server. "
    'Install them with: pip install -e ".[api]"'
)


def build_parser(settings: Settings | None = None) -> argparse.ArgumentParser:
    settings = settings or Settings()
    parser = argparse.ArgumentParser(description="DPM Agent API server")
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

    uvicorn.run(
        "agents.interfaces.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )
