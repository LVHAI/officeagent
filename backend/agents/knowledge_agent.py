"""
Knowledge Agent

负责企业知识库查询。
后续接入：
- Milvus
- RAG Pipeline
- Reranker
"""

from .base import BaseAgent, AgentContext, AgentResult


class KnowledgeAgent(BaseAgent):
    """企业知识检索 Agent。"""

    name = "knowledge-agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            # 当前返回模拟结果，后续替换为真实 RAG 检索流程
            return AgentResult(
                success=True,
                data={
                    "query": context.input,
                    "message": "Knowledge Agent 已接收查询"
                },
            )
        except Exception as exc:
            return self.handle_exception(exc)
