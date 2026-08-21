"""
Agent Runtime 基础抽象。

实现 Superpowers 计划 Phase 1:
- 统一 Agent 接口
- 统一上下文管理
- 统一结果返回
- 支持错误分类和后续重试机制
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentContext:
    """Agent 执行上下文。

    所有 Agent 共享该上下文，避免不同 Agent 使用不同参数结构。
    """

    task_id: str
    user_id: str
    input: str
    timeout: int = 60
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent 标准执行结果。

    不直接向上层抛异常，统一转换为结构化结果。
    """

    success: bool
    data: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    sources: list = field(default_factory=list)


class BaseAgent:
    """所有 Agent 的基础接口。"""

    name = "base-agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务。

        子类需要实现具体业务逻辑。
        """
        raise NotImplementedError

    def handle_exception(self, exc: Exception) -> AgentResult:
        """统一异常处理。

        后续 Retry/Circuit Breaker 根据 retryable 判断是否重试。
        """
        return AgentResult(
            success=False,
            error_code=exc.__class__.__name__,
            error_message=str(exc),
            retryable=True,
        )
