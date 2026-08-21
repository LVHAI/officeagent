from abc import ABC, abstractmethod

from .models import AgentContext, AgentResult


class BaseAgent(ABC):
    name: str = "base"

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            return await self.run(context)
        except Exception as exc:
            return AgentResult(
                success=False,
                error_code="AGENT_INTERNAL_ERROR",
                retryable=False,
                source_trace={"agent": self.name, "exception": str(exc)},
            )

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        pass


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    async def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            success=True,
            data={"task_id": context.task_id, "next": "planner"},
            source_trace={"agent": self.name},
        )
