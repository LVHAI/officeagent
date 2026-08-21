"""
Phase 6 - MCP Tool Framework

统一定义 Agent 可调用工具的数据协议。
支持：
- MCP Tool
- Internal Tool
- External API Tool

Agent 只依赖 Schema，不直接依赖工具实现。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ToolSchema:
    """工具能力描述。

    Tool Registry 会根据该结构发现工具，
    Executor 根据 timeout/retry 配置执行调用。
    """

    name: str
    description: str

    # 调用参数 JSON Schema
    input_schema: Dict[str, Any] = field(default_factory=dict)

    # 返回结果 JSON Schema
    output_schema: Dict[str, Any] = field(default_factory=dict)

    # 防止外部系统长时间阻塞 Agent
    timeout: int = 30

    # 是否允许 Executor 自动重试
    retry_enabled: bool = True

    # MCP Server 地址或标识
    mcp_server: Optional[str] = None


@dataclass
class ToolRequest:
    """统一工具调用请求。"""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class ToolResponse:
    """统一工具调用响应。

    retryable=True 时，Executor 可以进入 Retry 流程。
    """

    success: bool
    data: Any = None
    error_code: Optional[str] = None
    retryable: bool = False
