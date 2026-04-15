from agents.interfaces.cli.app import main, run_interactive_chat
from agents.interfaces.cli.parser import DEFAULT_THREAD_ID, build_parser
from agents.interfaces.cli.renderer import color as _color
from agents.interfaces.cli.renderer import render_stream as _render_stream

__all__ = [
    "DEFAULT_THREAD_ID",
    "build_parser",
    "main",
    "run_interactive_chat",
    "_color",
    "_render_stream",
]


if __name__ == "__main__":
    main()
