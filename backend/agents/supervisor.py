from typing import Any, Dict

from .base import AgentResult, BaseAgent


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        query = context.get("query", "")
        tasks = []
        if query:
            tasks.append("knowledge_retrieval")
            tasks.append("tool_execution")

        return AgentResult(
            success=True,
            data={"tasks": tasks},
            sources=[{"agent": self.name}],
        )
