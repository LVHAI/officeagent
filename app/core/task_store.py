from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryTaskStore:
    """Deterministic local fallback used for tests and development."""

    def __init__(self) -> None:
        self._items: dict[str, TaskRecord] = {}

    def save(self, record: TaskRecord) -> None:
        self._items[record.task_id] = record

    def get(self, task_id: str) -> TaskRecord | None:
        return self._items.get(task_id)
