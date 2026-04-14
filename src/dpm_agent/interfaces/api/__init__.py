from typing import Any
from importlib import import_module

__all__ = ["app", "create_app", "main"]


def __getattr__(name: str) -> Any:
    if name in {"app", "create_app"}:
        app_module = import_module("dpm_agent.interfaces.api.app")
        return getattr(app_module, name)
    if name == "main":
        from dpm_agent.interfaces.api.server import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
