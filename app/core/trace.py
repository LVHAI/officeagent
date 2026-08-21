from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentTrace:
    task_id: str
    agent_id: str
    parent_agent_id: str | None = None
    status: str = "running"
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    error: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)

    def finish(self, status: str = "completed", error: str | None = None) -> None:
        self.status = status
        self.error = error
        self.end_time = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolSource:
    system: str
    mcp_server: str
    tool: str
    request_id: str | None = None
    execution_time_ms: int | None = None
