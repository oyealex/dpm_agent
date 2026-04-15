from __future__ import annotations

import json
import sqlite3
from threading import RLock
from pathlib import Path
from typing import Any

from agents.domain.models import AgentEvent, Message, Page, ThreadSummary
from agents.sanitize import sanitize_metadata, sanitize_text
from agents.storage.db import Database


class ChatRepository:
    def __init__(self, database: Database | sqlite3.Connection, lock: RLock | None = None) -> None:
        self.database = _as_database(database)
        self.lock = lock or RLock()

    def ensure_thread(
        self,
        thread_id: str,
        title: str | None = None,
        user_id: str = "default",
    ) -> None:
        user_id = sanitize_text(user_id)
        thread_id = sanitize_text(thread_id)
        title = sanitize_text(title) if title is not None else None
        with self.lock:
            self.database.execute(
                """
                INSERT INTO threads(user_id, id, title)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, thread_id, title),
            )
            self.database.commit()

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        message_type: str = "message",
        metadata: dict[str, Any] | None = None,
        user_id: str = "default",
    ) -> None:
        user_id = sanitize_text(user_id)
        thread_id = sanitize_text(thread_id)
        self._add_message_rows(
            user_id,
            thread_id,
            [
                (
                    user_id,
                    thread_id,
                    sanitize_text(role),
                    sanitize_text(message_type),
                    sanitize_text(content),
                    _encode_metadata(metadata),
                )
            ],
        )

    def add_event(self, thread_id: str, event: AgentEvent, user_id: str = "default") -> None:
        self.add_message(
            thread_id=thread_id,
            role=event.role,
            content=event.content,
            message_type=event.event_type,
            metadata=event.metadata,
            user_id=user_id,
        )

    def add_events(
        self,
        thread_id: str,
        events: list[AgentEvent],
        user_id: str = "default",
    ) -> None:
        user_id = sanitize_text(user_id)
        thread_id = sanitize_text(thread_id)
        rows = [
            (
                user_id,
                thread_id,
                sanitize_text(event.role),
                sanitize_text(event.event_type),
                sanitize_text(event.content),
                _encode_metadata(event.metadata),
            )
            for event in events
            if event.persist
        ]
        if not rows:
            return
        self._add_message_rows(user_id, thread_id, rows)

    def _add_message_rows(
        self,
        user_id: str,
        thread_id: str,
        rows: list[tuple[Any, ...]],
    ) -> None:
        with self.lock:
            self.database.executemany(
                """
                INSERT INTO messages(user_id, thread_id, role, message_type, content, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self.database.execute(
                """
                UPDATE threads
                SET updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                  AND id = ?
                """,
                (user_id, thread_id),
            )
            self.database.commit()

    def list_messages(self, thread_id: str, user_id: str = "default") -> list[Message]:
        user_id = sanitize_text(user_id)
        thread_id = sanitize_text(thread_id)
        with self.lock:
            rows = self.database.execute(
                """
                SELECT role, content, message_type, metadata_json, created_at
                FROM messages
                WHERE user_id = ?
                  AND thread_id = ?
                  AND role IN ('user', 'assistant')
                  AND message_type IN ('message', 'user_message', 'assistant_message')
                ORDER BY id ASC
                """,
                (user_id, thread_id),
            ).fetchall()
        return [
            Message(
                role=sanitize_text(row["role"]),
                content=sanitize_text(row["content"]),
                message_type=sanitize_text(row["message_type"]),
                metadata=_decode_metadata(row["metadata_json"]),
                created_at=sanitize_text(row["created_at"]),
            )
            for row in rows
        ]

    def list_threads(self, user_id: str, limit: int = 50, offset: int = 0) -> Page:
        user_id = sanitize_text(user_id)
        limit = _normalize_limit(limit)
        offset = _normalize_offset(offset)
        with self.lock:
            rows = self.database.execute(
                """
                SELECT user_id, id, title, created_at, updated_at
                FROM threads
                WHERE user_id = ?
                ORDER BY updated_at DESC, id ASC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit + 1, offset),
            ).fetchall()
        return Page(
            items=[
                ThreadSummary(
                    user_id=sanitize_text(row["user_id"]),
                    thread_id=sanitize_text(row["id"]),
                    title=sanitize_text(row["title"]) if row["title"] is not None else None,
                    created_at=sanitize_text(row["created_at"]),
                    updated_at=sanitize_text(row["updated_at"]),
                )
                for row in rows[:limit]
            ],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    def list_thread_history(
        self,
        user_id: str,
        thread_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        user_id = sanitize_text(user_id)
        thread_id = sanitize_text(thread_id)
        limit = _normalize_limit(limit)
        offset = _normalize_offset(offset)
        with self.lock:
            rows = self.database.execute(
                """
                SELECT role, content, message_type, metadata_json, created_at
                FROM messages
                WHERE user_id = ?
                  AND thread_id = ?
                ORDER BY id ASC
                LIMIT ? OFFSET ?
                """,
                (user_id, thread_id, limit + 1, offset),
            ).fetchall()
        return Page(
            items=[
                Message(
                    role=sanitize_text(row["role"]),
                    content=sanitize_text(row["content"]),
                    message_type=sanitize_text(row["message_type"]),
                    metadata=_decode_metadata(row["metadata_json"]),
                    created_at=sanitize_text(row["created_at"]),
                )
                for row in rows[:limit]
            ],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )


class MemoryRepository:
    def __init__(self, database: Database | sqlite3.Connection, lock: RLock | None = None) -> None:
        self.database = _as_database(database)
        self.lock = lock or RLock()

    def sync_directory(self, memory_dir: Path) -> None:
        with self.lock:
            for path in sorted(memory_dir.rglob("*.md")):
                title = path.stem.replace("_", " ").replace("-", " ").strip().title()
                self.database.execute(
                    """
                    INSERT INTO memory_entries(path, title, tags)
                    VALUES (?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        title = excluded.title,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (str(path), title, ""),
                )
            self.database.commit()


def _decode_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        decoded = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return sanitize_metadata(decoded)
    return {}


def _encode_metadata(metadata: dict[str, Any] | None) -> str:
    return json.dumps(sanitize_metadata(metadata), ensure_ascii=False)


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, 100))


def _normalize_offset(offset: int) -> int:
    return max(0, offset)


def _as_database(database: Database | sqlite3.Connection) -> Database:
    if isinstance(database, Database):
        return database
    if isinstance(database, sqlite3.Connection):
        return Database(backend="sqlite", connection=database)
    raise TypeError(f"Unsupported database connection type: {type(database).__name__}")
