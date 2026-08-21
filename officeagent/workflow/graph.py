"""LangGraph 工作流编排入口。

当前实现提供基础状态流转能力，为后续 Supervisor Agent、
Multi-Agent 并发节点和 checkpoint 恢复提供扩展点。
"""

from typing import Callable, Dict

from .state import WorkflowState


class WorkflowGraph:
    """轻量工作流管理器。

    后续接入 LangGraph 后，该类负责封装 graph compile、
    node 注册以及状态持久化逻辑。
    """

    def __init__(self):
        # 保存 Agent 节点，key 为 Agent 名称
        self.nodes: Dict[str, Callable] = {}

    def register_node(self, name: str, handler: Callable):
        """注册一个工作流节点。"""
        self.nodes[name] = handler

    async def run(self, state: WorkflowState) -> WorkflowState:
        """执行当前状态对应的节点。

        异常不会直接抛出，统一记录到状态对象，
        保证上层可以执行恢复流程。
        """
        handler = self.nodes.get(state.current_agent)
        if handler is None:
            state.error = f"Agent node not found: {state.current_agent}"
            return state

        try:
            return await handler(state)
        except Exception as exc:
            # 工作流层捕获节点异常，避免整个任务崩溃
            state.error = str(exc)
            return state
