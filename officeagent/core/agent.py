"""Unified Agent runtime interfaces.

This module follows docs/plan.md stage one:
- unified async execute interface
- normalized result model
- controlled error handling
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


@dataclass
class AgentResult:
    """Standard result returned by every Agent execution."""

    success: bool
    data: Any = None
    error_code: Optional[str] = None
    retryable: bool = False
    source_trace: Dict[str, Any] = field(default_factory=dict)


class AgentException(Exception):
    """Base exception for expected Agent failures."""

    def __init__(self, message: str, error_code: str, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class BaseAgent(ABC):
    """All agents must implement this async execution contract."""

    name = "base"

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute agent and convert failures into unified results.

        Unhandled exceptions are intentionally contained here so a single
        agent failure does not crash the whole workflow.
        """
        try:
            return await self._execute(context)
        except AgentException as exc:
            return AgentResult(
                success=False,
                error_code=exc.error_code,
                retryable=exc.retryable,
            )
        except Exception:
            return AgentResult(
                success=False,
                error_code="INTERNAL_ERROR",
                retryable=False,
            )

    @abstractmethod
    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
