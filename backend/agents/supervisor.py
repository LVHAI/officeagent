"""
Supervisor Agent

负责：
1. 用户意图理解
2. 任务拆解
3. Agent 调度

当前阶段实现基础版本，为后续接入 LangGraph 做准备。
"""

from typing import List, Dict

from .base import BaseAgent, AgentContext, AgentResult


class SupervisorAgent(BaseAgent):
    """负责协调多个 Agent 的主管 Agent。"""

    name = "supervisor-agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            plan = self.create_plan(context.input)
            return AgentResult(
                success=True,
                data=plan,
            )
        except Exception as exc:
            return self.handle_exception(exc)

    def create_plan(self, query: str) -> List[Dict]:
        """
        创建任务计划。

        后续会由 LLM 进行智能规划，目前保留稳定接口。
        """
        tasks = []

        # 简单问题优先走知识库 Agent
        tasks.append({
            "agent": "knowledge-agent",
            "task": query,
        })

        # 包含分析关键词时增加工具调用
        if any(keyword in query for keyword in ["分析", "统计", "客户", "销售"]):
            tasks.append({
                "agent": "tool-agent",
                "task": query,
            })

        return tasks
