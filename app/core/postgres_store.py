from __future__ import annotations

from datetime import datetime

import psycopg

from app.core.audit import AuditEvent
from app.core.config import Settings, settings
from app.core.json_utils import dumps_json
from app.core.task_store import TaskRecord


class PostgresTaskStore:
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
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result JSONB,
                    error TEXT,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_audit_task_id ON agent_audit_events(task_id)"
            )
            conn.commit()

    def save(self, record: TaskRecord) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO agent_tasks(task_id, status, result, error, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    record.task_id,
                    record.status,
                    dumps_json(record.result) if record.result is not None else None,
                    record.error,
                    record.updated_at,
                ),
            )
            conn.commit()

    def append_audit(self, event: AuditEvent) -> None:
        """写入 Agent/MCP 审计事件；payload 统一存 JSONB 便于后续检索。"""
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO agent_audit_events(task_id, event_type, actor, payload, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    event.task_id,
                    event.event_type,
                    event.actor,
                    dumps_json(event.payload),
                    event.created_at,
                ),
            )
            conn.commit()

    def get(self, task_id: str) -> TaskRecord | None:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT task_id, status, result, error, updated_at FROM agent_tasks WHERE task_id = %s",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskRecord(
            task_id=row[0],
            status=row[1],
            result=row[2],
            error=row[3],
            updated_at=row[4] if isinstance(row[4], datetime) else datetime.fromisoformat(row[4]),
        )
