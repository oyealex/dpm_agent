from __future__ import annotations

import io
import os
import sys
from typing import TextIO


def _reconfigure_stream(stream: TextIO | None) -> None:
    if stream is None:
        return
    if not hasattr(stream, "reconfigure"):
        return
    if isinstance(stream, io.TextIOBase) and stream.closed:
        return
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        # 如果当前运行环境不允许重配（如已脱离底层缓冲区），则保持原状。
        return


def enforce_utf8_runtime() -> None:
    """Normalize runtime UTF-8 behavior for stdio and child-process defaults."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    _reconfigure_stream(sys.stdout)
    _reconfigure_stream(sys.stderr)
