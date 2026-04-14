from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from dpm_agent.models import AgentEvent, Message
from dpm_agent.sanitize import sanitize_metadata, sanitize_text


class ChatRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def ensure_thread(self, thread_id: str, title: str | None = None) -> None:
        thread_id = sanitize_text(thread_id)
        title = sanitize_text(title) if title is not None else None
        self.connection.execute(
            """
            INSERT INTO threads(id, title)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            """,
            (thread_id, title),
        )
        self.connection.commit()

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        message_type: str = "message",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        thread_id = sanitize_text(thread_id)
        self.connection.execute(
            """
            INSERT INTO messages(thread_id, role, message_type, content, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                sanitize_text(role),
                sanitize_text(message_type),
                sanitize_text(content),
                json.dumps(sanitize_metadata(metadata), ensure_ascii=False),
            ),
        )
        self.connection.execute(
            """
            UPDATE threads
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (thread_id,),
        )
        self.connection.commit()

    def add_event(self, thread_id: str, event: AgentEvent) -> None:
        self.add_message(
            thread_id=thread_id,
            role=event.role,
            content=event.content,
            message_type=event.event_type,
            metadata=event.metadata,
        )

    def add_events(self, thread_id: str, events: list[AgentEvent]) -> None:
        thread_id = sanitize_text(thread_id)
        rows = [
            (
                thread_id,
                sanitize_text(event.role),
                sanitize_text(event.event_type),
                sanitize_text(event.content),
                json.dumps(sanitize_metadata(event.metadata), ensure_ascii=False),
            )
            for event in events
            if event.persist
        ]
        if not rows:
            return
        self.connection.executemany(
            """
            INSERT INTO messages(thread_id, role, message_type, content, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.connection.execute(
            """
            UPDATE threads
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (thread_id,),
        )
        self.connection.commit()

    def list_messages(self, thread_id: str) -> list[Message]:
        thread_id = sanitize_text(thread_id)
        rows = self.connection.execute(
            """
            SELECT role, content, message_type, metadata_json
            FROM messages
            WHERE thread_id = ?
              AND role IN ('user', 'assistant')
              AND message_type IN ('message', 'user_message', 'assistant_message')
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
        return [
            Message(
                role=sanitize_text(row["role"]),
                content=sanitize_text(row["content"]),
                message_type=sanitize_text(row["message_type"]),
                metadata=_decode_metadata(row["metadata_json"]),
            )
            for row in rows
        ]


class MemoryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def sync_directory(self, memory_dir: Path) -> None:
        for path in sorted(memory_dir.rglob("*.md")):
            title = path.stem.replace("_", " ").replace("-", " ").strip().title()
            self.connection.execute(
                """
                INSERT INTO memory_entries(path, title, tags)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title = excluded.title,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(path), title, ""),
            )
        self.connection.commit()


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
