from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import psycopg

from app.core.config import Settings, settings
from app.core.json_utils import dumps_json
from app.core.memory import LongTermMemory


class PostgresMemoryStore:
    """Persistent raw conversation, short-term summary, and long-term memory store."""

    def __init__(self, current: Settings = settings) -> None:
        self.dsn = f"host={current.postgres_host} port={current.postgres_port} dbname={current.postgres_db} user={current.postgres_user} password={current.postgres_password}"

    def setup(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_sessions (session_id TEXT PRIMARY KEY, user_id TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_messages (message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES conversation_sessions(session_id) ON DELETE CASCADE, user_id TEXT, role TEXT NOT NULL, content TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_session ON conversation_messages(session_id, created_at)")
            conn.execute("CREATE TABLE IF NOT EXISTS short_term_memory (session_id TEXT PRIMARY KEY REFERENCES conversation_sessions(session_id) ON DELETE CASCADE, summary TEXT, updated_at TIMESTAMPTZ NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS long_term_memories (memory_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, memory_type TEXT NOT NULL, memory_key TEXT NOT NULL, memory_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL, source_message_id TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, UNIQUE(user_id, memory_type, memory_key))")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_long_term_memories_user ON long_term_memories(user_id, updated_at DESC)")
            conn.commit()

    def ensure_session(self, session_id: str, user_id: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        with psycopg.connect(self.dsn) as conn:
            conn.execute("INSERT INTO conversation_sessions(session_id, user_id, created_at, updated_at) VALUES (%s, %s, %s, %s) ON CONFLICT(session_id) DO UPDATE SET user_id = COALESCE(EXCLUDED.user_id, conversation_sessions.user_id), updated_at = EXCLUDED.updated_at", (session_id, user_id, now, now))
            conn.commit()

    def get_session(self, session_id: str) -> dict | None:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute("SELECT session_id, user_id, created_at, updated_at FROM conversation_sessions WHERE session_id = %s", (session_id,)).fetchone()
        return {"session_id": row[0], "user_id": row[1], "created_at": row[2].isoformat(), "updated_at": row[3].isoformat()} if row else None

    def delete_session(self, session_id: str) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute("DELETE FROM conversation_sessions WHERE session_id = %s", (session_id,))
            conn.commit()

    def list_sessions(self, user_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        with psycopg.connect(self.dsn) as conn:
            if user_id:
                rows = conn.execute("SELECT session_id, user_id, created_at, updated_at FROM conversation_sessions WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s OFFSET %s", (user_id, limit, offset)).fetchall()
            else:
                rows = conn.execute("SELECT session_id, user_id, created_at, updated_at FROM conversation_sessions ORDER BY updated_at DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        return [{"session_id": row[0], "user_id": row[1], "created_at": row[2].isoformat(), "updated_at": row[3].isoformat()} for row in rows]

    def append_message(self, session_id: str, role: str, content: str, *, user_id: str | None = None, message_id: str | None = None, metadata: dict | None = None) -> str:
        self.ensure_session(session_id, user_id)
        message_id = message_id or str(uuid4())
        now = datetime.now(timezone.utc)
        with psycopg.connect(self.dsn) as conn:
            conn.execute("INSERT INTO conversation_messages(message_id, session_id, user_id, role, content, metadata, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT(message_id) DO NOTHING", (message_id, session_id, user_id, role, content, dumps_json(metadata or {}), now))
            conn.execute("UPDATE conversation_sessions SET updated_at = %s WHERE session_id = %s", (now, session_id))
            conn.commit()
        return message_id

    def recent_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute("SELECT message_id, role, content, metadata, created_at FROM conversation_messages WHERE session_id = %s ORDER BY created_at DESC LIMIT %s", (session_id, limit)).fetchall()
        return [{"message_id": row[0], "role": row[1], "content": row[2], "metadata": row[3] or {}, "created_at": row[4].isoformat()} for row in reversed(rows)]

    def list_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
        if limit < 1 or offset < 0:
            raise ValueError("limit must be >= 1 and offset must be >= 0")
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute("SELECT message_id, role, content, metadata, created_at FROM conversation_messages WHERE session_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s", (session_id, limit, offset)).fetchall()
        return [{"message_id": row[0], "role": row[1], "content": row[2], "metadata": row[3] or {}, "created_at": row[4].isoformat()} for row in rows]

    def get_summary(self, session_id: str) -> str | None:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute("SELECT summary FROM short_term_memory WHERE session_id = %s", (session_id,)).fetchone()
        return row[0] if row else None

    def save_summary(self, session_id: str, summary: str) -> None:
        now = datetime.now(timezone.utc)
        self.ensure_session(session_id)
        with psycopg.connect(self.dsn) as conn:
            conn.execute("INSERT INTO short_term_memory(session_id, summary, updated_at) VALUES (%s, %s, %s) ON CONFLICT(session_id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = EXCLUDED.updated_at", (session_id, summary, now))
            conn.commit()

    def upsert_long_term_memory(self, item: dict) -> LongTermMemory:
        now = datetime.now(timezone.utc)
        memory_id = str(uuid4())
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute("INSERT INTO long_term_memories(memory_id, user_id, memory_type, memory_key, memory_value, confidence, source_message_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT(user_id, memory_type, memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value, confidence = EXCLUDED.confidence, source_message_id = EXCLUDED.source_message_id, updated_at = EXCLUDED.updated_at RETURNING memory_id, user_id, memory_type, memory_key, memory_value, confidence, source_message_id, created_at, updated_at", (memory_id, item["user_id"], item["memory_type"], item["key"], item["value"], float(item.get("confidence", 0.5)), item.get("source_message_id"), now, now)).fetchone()
            conn.commit()
        return LongTermMemory(memory_id=row[0], user_id=row[1], memory_type=row[2], key=row[3], value=row[4], confidence=row[5], source_message_id=row[6], created_at=row[7], updated_at=row[8])

    def list_long_term_memories(self, user_id: str, limit: int = 20) -> list[LongTermMemory]:
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute("SELECT memory_id, user_id, memory_type, memory_key, memory_value, confidence, source_message_id, created_at, updated_at FROM long_term_memories WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s", (user_id, limit)).fetchall()
        return [LongTermMemory(memory_id=row[0], user_id=row[1], memory_type=row[2], key=row[3], value=row[4], confidence=row[5], source_message_id=row[6], created_at=row[7], updated_at=row[8]) for row in rows]
