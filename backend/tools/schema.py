"""
Tool 参数和返回结构定义。
用于统一 MCP Tool、Skill Tool、内部工具的数据协议。
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolRequest:
    """工具调用请求。

    通过统一结构避免不同 Agent 传递参数格式不一致。
    """

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class ToolResponse:
    """工具调用响应。

    error_code 用于上层判断是否需要重试。
    """

    success: bool
    data: Any = None
    error_code: str | None = None
    retryable: bool = False
