from __future__ import annotations

import json

import psycopg

from app.core.config import Settings, settings


class PostgresAuditStore:
    """将 Agent Trace 和工具来源写入 PostgreSQL，便于审计与故障追踪。"""

    def __init__(self, current: Settings = settings) -> None:
        self.dsn = (
            f"host={current.postgres_host} port={current.postgres_port} "
            f"dbname={current.postgres_db} user={current.postgres_user} "
            f"password={current.postgres_password}"
        )

    def setup(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_id TEXT,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_audit_task_id ON agent_audit_events(task_id)"
            )
            conn.commit()

    def append(self, task_id: str, event_type: str, payload: dict, agent_id: str | None = None) -> None:
        """追加审计事件而不是覆盖旧记录，保留完整执行时间线。"""
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO agent_audit_events(task_id, event_type, agent_id, payload)
                VALUES (%s, %s, %s, %s)
                """,
                (task_id, event_type, agent_id, json.dumps(payload)),
            )
            conn.commit()
