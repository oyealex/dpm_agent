from __future__ import annotations

from typing import Any


def sanitize_text(value: str) -> str:
    """Return text that is safe to send as UTF-8 JSON.

    Python may represent undecodable stdin bytes as low surrogate code points
    via surrogateescape. Rebuild those bytes first so valid UTF-8 input such as
    Chinese quotes is preserved, then replace only genuinely invalid sequences.
    """
    if not _has_surrogate(value):
        return value
    try:
        return value.encode("utf-8", errors="surrogateescape").decode(
            "utf-8",
            errors="replace",
        )
    except UnicodeEncodeError:
        return value.encode("utf-8", errors="replace").decode("utf-8")


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if value is None or isinstance(value, int | float | bool):
        return value
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_text(str(key)): sanitize_json_value(item)
            for key, item in value.items()
        }
    return sanitize_text(str(value))


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    value = sanitize_json_value(metadata or {})
    if isinstance(value, dict):
        return value
    return {}


def _has_surrogate(value: str) -> bool:
    return any("\ud800" <= char <= "\udfff" for char in value)
