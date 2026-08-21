"""
Agent 路由器。

根据 Supervisor 的规划结果，将任务发送到对应 Agent。
"""


class AgentRouter:
    def __init__(self):
        self.routes = {}

    def register(self, name, agent):
        """注册 Agent。"""
        self.routes[name] = agent

    def route(self, name):
        """获取目标 Agent。"""
        return self.routes.get(name)
