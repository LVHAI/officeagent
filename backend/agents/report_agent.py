"""
Report Agent

负责聚合多个 Agent 结果并生成最终报告。
"""

from .base import BaseAgent, AgentContext, AgentResult


class ReportAgent(BaseAgent):
    """分析报告生成 Agent。"""

    name = "report-agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            return AgentResult(
                success=True,
                data={
                    "title": "企业智能分析报告",
                    "content": context.input,
                    "sources": [],
                },
            )
        except Exception as exc:
            return self.handle_exception(exc)
