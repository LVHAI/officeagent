"""
LangGraph 工作流状态定义。

对应 Superpowers Phase 2:
- Agent 状态统一管理
- 支持多 Agent 协作
- 支持 checkpoint 恢复
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentState:
    """Agent 工作流状态。

    LangGraph 中每个节点共享该状态对象。
    通过统一状态避免 Agent 之间传递不可控数据。
    """

    task_id: str
    user_input: str

    # 当前正在执行的 Agent 名称
    current_agent: str = ""

    # 保存所有 Agent 输出结果
    results: List[Any] = field(default_factory=list)

    # 保存异常信息，便于后续分析和恢复
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # checkpoint 标识，用于任务恢复
    checkpoint_id: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)
