"""
Tool 基础定义。
所有企业工具、MCP工具都实现统一接口，方便 Agent 调度。
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolResult:
    """工具执行统一返回结果，避免异常直接向上冒泡。"""
    success: bool
    data: Any = None
    error: str | None = None
    retryable: bool = False


class BaseTool:
    """所有 Tool 的基础抽象类。"""

    name: str = "base"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        raise NotImplementedError
