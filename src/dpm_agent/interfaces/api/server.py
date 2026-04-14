from __future__ import annotations

import argparse
import importlib.util


INSTALL_API_MESSAGE = (
    "API dependencies are required to run the API server. "
    'Install them with: pip install -e ".[api]"'
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DPM Agent API server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind, defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind, defaults to 8000.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reload the server when source files change.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if importlib.util.find_spec("fastapi") is None:
        raise SystemExit(INSTALL_API_MESSAGE)

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(INSTALL_API_MESSAGE) from exc

    uvicorn.run(
        "dpm_agent.interfaces.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )
