from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.config import Settings


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'message',
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES threads(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_id_id
ON messages(thread_id, id);

CREATE TABLE IF NOT EXISTS memory_entries (
    path TEXT PRIMARY KEY,
    title TEXT,
    tags TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA = SQLITE_SCHEMA

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    role TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'message',
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_id_id
ON messages(thread_id, id);

CREATE TABLE IF NOT EXISTS memory_entries (
    path TEXT PRIMARY KEY,
    title TEXT,
    tags TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass
class Database:
    backend: str
    connection: Any

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self.connection.execute(self._prepare_sql(sql), params)

    def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> Any:
        prepared_sql = self._prepare_sql(sql)
        if self.backend == "postgres":
            with self.connection.cursor() as cursor:
                return cursor.executemany(prepared_sql, rows)
        return self.connection.executemany(prepared_sql, rows)

    def commit(self) -> None:
        self.connection.commit()

    def executescript(self, sql: str) -> None:
        if self.backend == "sqlite":
            self.connection.executescript(sql)
            return
        with self.connection.cursor() as cursor:
            for statement in _split_sql_script(sql):
                cursor.execute(statement)

    def _prepare_sql(self, sql: str) -> str:
        if self.backend == "postgres":
            return sql.replace("?", "%s")
        return sql


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def connect_database(settings: Settings) -> Database:
    backend = settings.effective_storage_backend
    if backend == "sqlite":
        return Database(backend="sqlite", connection=connect(settings.effective_db_path))
    if backend == "postgres":
        dsn = settings.effective_postgres_dsn
        if not dsn:
            raise ValueError(
                "PostgreSQL storage requires AGENT_POSTGRES_DSN."
            )
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL storage requires psycopg. "
                'Install it with: pip install -e ".[postgres]"'
            ) from exc
        connection = psycopg.connect(dsn, row_factory=dict_row)
        return Database(backend="postgres", connection=connection)
    raise ValueError(f"Unsupported storage backend: {backend}")


def initialize_database(database: sqlite3.Connection | Database) -> None:
    if isinstance(database, sqlite3.Connection):
        database.executescript(SQLITE_SCHEMA)
        _ensure_sqlite_column(database, "messages", "message_type", "TEXT NOT NULL DEFAULT 'message'")
        _ensure_sqlite_column(database, "messages", "metadata_json", "TEXT")
        database.commit()
        return

    if database.backend == "sqlite":
        database.executescript(SQLITE_SCHEMA)
        _ensure_sqlite_column(
            database.connection,
            "messages",
            "message_type",
            "TEXT NOT NULL DEFAULT 'message'",
        )
        _ensure_sqlite_column(database.connection, "messages", "metadata_json", "TEXT")
        database.commit()
        return

    if database.backend == "postgres":
        database.executescript(POSTGRES_SCHEMA)
        database.commit()
        return

    raise ValueError(f"Unsupported storage backend: {database.backend}")


def _ensure_sqlite_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column["name"] == column_name for column in columns):
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _split_sql_script(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]
