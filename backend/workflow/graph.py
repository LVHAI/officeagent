"""
LangGraph 工作流编排入口。

负责定义：
- Supervisor 调度
- Agent 节点连接
- 状态流转

当前保留框架结构，后续接入真实 LangGraph。
"""


class AgentWorkflowGraph:
    """Agent 工作流图。

    后续会由 LangGraph StateGraph 实现。
    """

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, name, handler):
        """注册 Agent 节点。"""
        self.nodes[name] = handler

    def add_edge(self, source, target):
        """定义 Agent 执行关系。"""
        self.edges.append((source, target))

    async def execute(self, state):
        """执行工作流。

        后续版本会替换为 LangGraph Runtime。
        """
        return state
