from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol


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
