"""
Tool 注册中心。
Agent 不直接依赖具体工具，通过 Registry 动态发现能力。
"""


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)
