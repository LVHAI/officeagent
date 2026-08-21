"""
Tool Agent

负责企业系统工具调用。
后续接入：
- MCP Client
- Skill Router
- 企业 API
"""

from .base import BaseAgent, AgentContext, AgentResult


class ToolAgent(BaseAgent):
    """企业工具调用 Agent。"""

    name = "tool-agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            # 后续这里会调用 MCP Server
            return AgentResult(
                success=True,
                data={
                    "message": "Tool Agent 已准备执行工具调用",
                    "query": context.input,
                },
            )
        except Exception as exc:
            return self.handle_exception(exc)
