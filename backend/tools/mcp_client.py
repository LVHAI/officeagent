"""
MCP Client implementation.

负责 Agent Tool Layer 与 MCP Server 的通信。
通过统一接口隔离 Agent 和底层 MCP transport。
"""

from typing import Any, Dict

from .schema import ToolRequest, ToolResponse


class MCPClientError(Exception):
    """MCP 调用异常。"""


class MCPClient:
    """
    MCP 服务调用客户端。

    后续可以接入真实 JSON-RPC / HTTP / WebSocket transport。
    当前保持稳定接口，方便 Executor 调用。
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def call(self, method: str, params: Dict[str, Any]):
        """调用 MCP 方法。

        这里负责协议层封装。
        timeout、retry、circuit breaker 在后续阶段接入。
        """
        return {
            "method": method,
            "params": params,
            "endpoint": self.endpoint,
        }

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """通过 MCP 协议执行 Tool。

        将 MCP 返回结果转换成统一 ToolResponse，
        避免 Agent 感知底层协议差异。
        """
        try:
            result = await self.call(
                request.tool_name,
                request.arguments,
            )
            return ToolResponse(success=True, data=result)
        except Exception as exc:
            return ToolResponse(
                success=False,
                error_code=str(exc),
                retryable=True,
            )
