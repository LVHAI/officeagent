from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentResult:
    """Agent 执行结果统一模型。

    所有 Agent 的执行结果都必须通过该结构返回，避免异常直接向上层传播。
    同时携带错误信息、重试策略以及来源追踪信息，方便后续审计和恢复。
    """

    # 标识当前 Agent 执行是否成功。
    success: bool

    # Agent 返回的业务数据，可以是文本、结构化数据或工具调用结果。
    data: Any = None

    # 标准化错误码，用于错误分类和监控告警。
    error_code: Optional[str] = None

    # 标识当前失败是否允许调度器自动重试。
    retryable: bool = False

    # 来源追踪信息，例如 Agent 名称、工具调用链路等。
    source_trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Agent 执行上下文。

    Context 会在多个 Agent 节点之间传递，保存任务身份、输入数据以及扩展元信息。
    """

    # 全链路任务唯一 ID，用于状态追踪和 checkpoint 恢复。
    task_id: str

    # 当前任务输入参数。
    payload: Dict[str, Any]

    # 扩展上下文，例如用户信息、权限、环境配置等。
    metadata: Dict[str, Any] = field(default_factory=dict)
