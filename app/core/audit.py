from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AuditEvent:
    task_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime


class AuditStore(Protocol):
    """审计事件存储接口，便于本地内存实现和 PostgreSQL 实现切换。"""

    def append(self, event: AuditEvent) -> None: ...


class InMemoryAuditStore:
    """本地开发用审计存储；线程安全地保存 Agent/MCP 执行事件。"""

    def __init__(self) -> None:
        from threading import Lock

        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list(self, task_id: str) -> list[AuditEvent]:
        with self._lock:
            return [event for event in self._events if event.task_id == task_id]


def make_audit_event(task_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        task_id=task_id,
        event_type=event_type,
        actor=actor,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
