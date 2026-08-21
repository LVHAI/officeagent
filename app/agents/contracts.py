from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Source:
    kind: str
    title: str = ""
    uri: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentInput:
    task_id: str
    query: str
    parent_agent_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    agent_id: str
    status: str
    result: Any = None
    sources: list[Source] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass(frozen=True)
class DelegationTrace:
    task_id: str
    delegation_id: str
    parent_agent_id: str
    child_agent_id: str
    status: str
    reason: str = ""
    elapsed_ms: float = 0.0
    error: str | None = None
