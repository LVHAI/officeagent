"""LangGraph 工作流状态定义。

阶段二要求保存：
- task_id
- 当前 Agent
- 执行结果
- 错误信息
- checkpoint 信息
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class WorkflowState:
    """工作流节点之间共享的状态对象。"""

    # 当前任务唯一标识，用于恢复和审计
    task_id: str

    # 当前正在执行的 Agent 名称
    current_agent: str = ""

    # Agent 执行历史结果
    results: List[Any] = field(default_factory=list)

    # 当前错误信息，失败恢复时使用
    error: str | None = None

    # checkpoint 数据，用于断点恢复
    checkpoint: Dict[str, Any] = field(default_factory=dict)
