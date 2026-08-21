from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol

from app.core.config import Settings, settings


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TaskStore(Protocol):
    """任务状态存储接口，便于本地开发和生产持久化实现互换。"""

    def save(self, record: TaskRecord) -> None: ...

    def get(self, task_id: str) -> TaskRecord | None: ...


class InMemoryTaskStore:
    """本地开发/测试使用的线程安全任务存储，不依赖外部数据库。"""

    def __init__(self) -> None:
        self._items: dict[str, TaskRecord] = {}
        self._lock = Lock()

    def save(self, record: TaskRecord) -> None:
        with self._lock:
            self._items[record.task_id] = record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._items.get(task_id)


class PostgresTaskStore:
    """PostgreSQL 任务存储；同步 SQL 在独立线程中执行，避免阻塞 async Agent。"""

    def __init__(self, current: Settings = settings) -> None:
        self._dsn = (
            f"postgresql://{current.postgres_user}:{current.postgres_password}"
            f"@{current.postgres_host}:{current.postgres_port}/{current.postgres_db}"
        )

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def setup(self) -> None:
        """创建任务表；生产部署可迁移到正式 migration 工具。"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
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
            conn.commit()

    def save(self, record: TaskRecord) -> None:
        import json

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_tasks (task_id, status, result, error, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (task_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        record.task_id,
                        record.status,
                        json.dumps(record.result) if record.result is not None else None,
                        record.error,
                        record.updated_at,
                    ),
                )
            conn.commit()

    def get(self, task_id: str) -> TaskRecord | None:
        import json

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT task_id, status, result, error, updated_at FROM agent_tasks WHERE task_id = %s",
                    (task_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        result = row[2]
        if isinstance(result, str):
            result = json.loads(result)
        return TaskRecord(
            task_id=row[0],
            status=row[1],
            result=result,
            error=row[3],
            updated_at=row[4],
        )
