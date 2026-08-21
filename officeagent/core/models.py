from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error_code: Optional[str] = None
    retryable: bool = False
    source_trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    task_id: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
