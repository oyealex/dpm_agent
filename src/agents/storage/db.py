from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.config import Settings


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    user_id TEXT NOT NULL DEFAULT 'default',
    id TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'message',
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id, thread_id) REFERENCES threads(user_id, id)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_id_id
ON messages(user_id, thread_id, id);

CREATE INDEX IF NOT EXISTS idx_threads_user_updated
ON threads(user_id, updated_at DESC, id);

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
    user_id TEXT NOT NULL DEFAULT 'default',
    id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, id)
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'message',
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id, thread_id) REFERENCES threads(user_id, id)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_id_id
ON messages(user_id, thread_id, id);

CREATE INDEX IF NOT EXISTS idx_threads_user_updated
ON threads(user_id, updated_at DESC, id);

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
        _migrate_sqlite_user_scope(database)
        database.executescript(SQLITE_SCHEMA)
        _ensure_sqlite_message_columns(database)
        database.commit()
        return

    if database.backend == "sqlite":
        _migrate_sqlite_user_scope(database.connection)
        database.executescript(SQLITE_SCHEMA)
        _ensure_sqlite_message_columns(database.connection)
        database.commit()
        return

    if database.backend == "postgres":
        database.executescript(POSTGRES_SCHEMA)
        _migrate_postgres_user_scope(database)
        database.commit()
        return

    raise ValueError(f"Unsupported storage backend: {database.backend}")


def _ensure_sqlite_message_columns(connection: sqlite3.Connection) -> None:
    _ensure_sqlite_column(connection, "messages", "user_id", "TEXT NOT NULL DEFAULT 'default'")
    _ensure_sqlite_column(connection, "messages", "message_type", "TEXT NOT NULL DEFAULT 'message'")
    _ensure_sqlite_column(connection, "messages", "metadata_json", "TEXT")


def _migrate_sqlite_user_scope(connection: sqlite3.Connection) -> None:
    if not _sqlite_table_exists(connection, "threads"):
        return

    if not _sqlite_threads_need_rebuild(connection):
        _ensure_sqlite_column(connection, "messages", "user_id", "TEXT NOT NULL DEFAULT 'default'")
        return

    connection.execute("PRAGMA foreign_keys = OFF")
    _rebuild_sqlite_threads(connection)
    if _sqlite_table_exists(connection, "messages"):
        _rebuild_sqlite_messages(connection)
    connection.execute("PRAGMA foreign_keys = ON")


def _sqlite_table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _sqlite_threads_need_rebuild(connection: sqlite3.Connection) -> bool:
    columns = connection.execute("PRAGMA table_info(threads)").fetchall()
    pk_columns = [
        (column["pk"], column["name"])
        for column in columns
        if column["pk"]
    ]
    return pk_columns != [(1, "user_id"), (2, "id")]


def _rebuild_sqlite_threads(connection: sqlite3.Connection) -> None:
    columns = {column["name"] for column in connection.execute("PRAGMA table_info(threads)").fetchall()}
    user_expr = "COALESCE(user_id, 'default')" if "user_id" in columns else "'default'"
    connection.execute("ALTER TABLE threads RENAME TO threads_old_user_scope")
    connection.execute(
        """
        CREATE TABLE threads (
            user_id TEXT NOT NULL DEFAULT 'default',
            id TEXT NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT OR REPLACE INTO threads(user_id, id, title, created_at, updated_at)
        SELECT {user_expr}, id, title, created_at, updated_at
        FROM threads_old_user_scope
        """
    )
    connection.execute("DROP TABLE threads_old_user_scope")


def _rebuild_sqlite_messages(connection: sqlite3.Connection) -> None:
    columns = {column["name"] for column in connection.execute("PRAGMA table_info(messages)").fetchall()}
    user_expr = "COALESCE(user_id, 'default')" if "user_id" in columns else "'default'"
    message_type_expr = (
        "message_type"
        if "message_type" in columns
        else "'message'"
    )
    metadata_expr = "metadata_json" if "metadata_json" in columns else "NULL"

    connection.execute("ALTER TABLE messages RENAME TO messages_old_user_scope")
    connection.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'message',
            content TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id, thread_id) REFERENCES threads(user_id, id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO messages(id, user_id, thread_id, role, message_type, content, metadata_json, created_at)
        SELECT id, {user_expr}, thread_id, role, {message_type_expr}, content, {metadata_expr}, created_at
        FROM messages_old_user_scope
        """
    )
    connection.execute("DROP TABLE messages_old_user_scope")


def _migrate_postgres_user_scope(database: Database) -> None:
    statements = [
        "ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_thread_id_fkey",
        "ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_user_id_thread_id_fkey",
        "ALTER TABLE threads ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default'",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default'",
        "ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_pkey",
        "ALTER TABLE threads ADD PRIMARY KEY (user_id, id)",
        """
        ALTER TABLE messages
        ADD CONSTRAINT messages_user_id_thread_id_fkey
        FOREIGN KEY(user_id, thread_id) REFERENCES threads(user_id, id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_messages_thread_id_id
        ON messages(user_id, thread_id, id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_threads_user_updated
        ON threads(user_id, updated_at DESC, id)
        """,
    ]
    for statement in statements:
        database.execute(statement)


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
