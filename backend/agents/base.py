from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error_code: str | None = None
    retryable: bool = False
    sources: list[Dict[str, Any]] = field(default_factory=list)


class BaseAgent:
    name = "base"

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
