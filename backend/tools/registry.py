"""
Tool Registry Framework.

负责管理 Agent 可调用的工具，包括：
- MCP Tools
- Internal Tools
- External API Tools

Registry 作为 Tool 调度入口，避免 Agent 直接依赖具体实现。
"""

from typing import Dict, List

from .schema import ToolSchema


class ToolRegistryError(Exception):
    """Tool Registry 基础异常。"""


class DuplicateToolError(ToolRegistryError):
    """工具重复注册异常。"""


class ToolNotFoundError(ToolRegistryError):
    """工具不存在异常。"""


class ToolRegistry:
    """统一 Tool 注册中心。

    MCP Client、Executor 等模块通过 Registry 获取工具定义。
    """

    def __init__(self):
        self._tools: Dict[str, ToolSchema] = {}

    def register(self, tool: ToolSchema) -> None:
        """注册 Tool。

        不允许覆盖已有 Tool，避免 Agent 调用错误版本。
        """
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSchema:
        """根据名称获取 Tool。"""
        if name not in self._tools:
            raise ToolNotFoundError(name)

        return self._tools[name]

    def remove(self, name: str) -> None:
        """删除 Tool。"""
        if name not in self._tools:
            raise ToolNotFoundError(name)

        del self._tools[name]

    def list_tools(self) -> List[ToolSchema]:
        """返回全部已注册 Tool。"""
        return list(self._tools.values())
