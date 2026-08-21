from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.reliability import CircuitBreaker, retry_async


class MCPTransport(Protocol):
    async def list_tools(self) -> Any: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class MCPTool:
    """统一 MCP Tool 描述，避免 Agent 直接依赖具体 MCP SDK 对象。"""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPClient:
    """MCP Client：Discovery/Invocation + timeout/retry/circuit-breaker。"""

    def __init__(
        self,
        transport: MCPTransport,
        timeout_seconds: float = 30.0,
        retry_attempts: int = 3,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.breaker = breaker or CircuitBreaker()

    async def discover_tools(self) -> list[MCPTool]:
        async def operation():
            return await asyncio.wait_for(self.transport.list_tools(), timeout=self.timeout_seconds)

        try:
            response = await retry_async(
                operation, attempts=self.retry_attempts, breaker=self.breaker
            )
            tools = getattr(response, "tools", response)
            return [
                MCPTool(
                    name=str(tool.name),
                    description=str(getattr(tool, "description", "")),
                    input_schema=dict(
                        getattr(tool, "inputSchema", getattr(tool, "input_schema", {})) or {}
                    ),
                )
                for tool in tools
            ]
        except asyncio.TimeoutError as exc:
            raise MCPTimeoutError("MCP tool discovery timed out") from exc
        except Exception as exc:  # noqa: BLE001 - 边界层统一归一化第三方异常
            if isinstance(exc, MCPError):
                raise
            raise MCPError(f"MCP tool discovery failed: {exc}") from exc

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        async def operation():
            return await asyncio.wait_for(
                self.transport.call_tool(tool_name, arguments), timeout=self.timeout_seconds
            )

        try:
            return await retry_async(operation, attempts=self.retry_attempts, breaker=self.breaker)
        except asyncio.TimeoutError as exc:
            raise MCPTimeoutError(f"MCP tool invocation timed out: {tool_name}") from exc
        except Exception as exc:  # noqa: BLE001 - 边界层统一归一化第三方异常
            if isinstance(exc, MCPError):
                raise
            raise MCPError(f"MCP tool invocation failed: {tool_name}: {exc}") from exc


class MCPError(RuntimeError):
    """MCP 边界统一异常。"""


class MCPTimeoutError(MCPError):
    """MCP 操作超时。"""
