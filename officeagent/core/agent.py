from abc import ABC, abstractmethod

from .models import AgentContext, AgentResult


class BaseAgent(ABC):
    """所有 Agent 的基础抽象类。

    定义统一执行入口，负责异常隔离和结果标准化。
    具体 Agent 只需要实现 run 方法即可。
    """

    # Agent 唯一名称，用于日志、追踪和监控。
    name: str = "base"

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务。

        该方法作为统一入口：
        1. 捕获 Agent 内部异常；
        2. 转换为标准 AgentResult；
        3. 防止未处理异常影响整个工作流。
        """
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
        """Agent 核心业务逻辑实现。

        子类必须实现该方法。
        """
        pass


class SupervisorAgent(BaseAgent):
    """Supervisor Agent。

    负责接收用户任务并进行后续任务规划，是 Multi-Agent 系统入口节点。
    """

    name = "supervisor"

    async def run(self, context: AgentContext) -> AgentResult:
        # 当前阶段仅完成任务规划入口，后续将接入 LangGraph 编排。
        return AgentResult(
            success=True,
            data={"task_id": context.task_id, "next": "planner"},
            source_trace={"agent": self.name},
        )
