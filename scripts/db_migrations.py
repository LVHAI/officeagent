from __future__ import annotations

import psycopg

from app.core.config import settings

MIGRATION_VERSION = "001_user_auth_conversation"

STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE IF NOT EXISTS auth_sessions (session_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, last_used_at TIMESTAMPTZ NOT NULL)",
    "ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS session_id TEXT",
    "ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ",
    "UPDATE auth_sessions SET session_id=COALESCE(session_id,md5(token_hash)), last_used_at=COALESCE(last_used_at,created_at) WHERE session_id IS NULL OR last_used_at IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_sessions_session_id ON auth_sessions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)",
    "CREATE TABLE IF NOT EXISTS conversation_sessions (session_id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE, title TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)",
    "ALTER TABLE conversation_sessions ADD COLUMN IF NOT EXISTS title TEXT",
    "CREATE TABLE IF NOT EXISTS conversation_messages (message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES conversation_sessions(session_id) ON DELETE CASCADE, user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user_updated ON conversation_sessions(user_id,updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_created ON conversation_messages(session_id,created_at)",
    "CREATE TABLE IF NOT EXISTS short_term_memory (session_id TEXT PRIMARY KEY REFERENCES conversation_sessions(session_id) ON DELETE CASCADE, summary TEXT, updated_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE IF NOT EXISTS long_term_memories (memory_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, memory_type TEXT NOT NULL, memory_key TEXT NOT NULL, memory_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL, source_message_id TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, UNIQUE(user_id,memory_type,memory_key))",
    "CREATE INDEX IF NOT EXISTS idx_long_term_memories_user ON long_term_memories(user_id,updated_at DESC)",
)


def apply_migrations() -> None:
    with psycopg.connect(settings.postgres_dsn) as conn:
        conn.execute(STATEMENTS[0])
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (MIGRATION_VERSION,)).fetchone():
            conn.commit()
            return
        for statement in STATEMENTS[1:]:
            conn.execute(statement)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (MIGRATION_VERSION,))
        conn.commit()


if __name__ == "__main__":
    apply_migrations()
