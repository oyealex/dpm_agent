from typing import Any
from importlib import import_module

from agents.runtime_encoding import enforce_utf8_runtime

__all__ = ["app", "create_app", "main"]


def __getattr__(name: str) -> Any:
    if name in {"app", "create_app"}:
        app_module = import_module("agents.interfaces.api.app")
        return getattr(app_module, name)
    if name == "main":
        from agents.interfaces.api.server import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    enforce_utf8_runtime()
    from agents.interfaces.api.server import main as run_server

    run_server()


if __name__ == "__main__":
    main()
