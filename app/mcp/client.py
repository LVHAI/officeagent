from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPError(RuntimeError):
    """MCP 调用统一异常，避免 SDK 异常直接泄漏到 Agent 层。"""


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    server: str


class MCPClient:
    """MCP Streamable HTTP Client，负责发现工具、调用工具及基础超时。"""

    def __init__(self, server: str, url: str, *, timeout: float = 15.0) -> None:
        self.server = server
        self.url = url
        self.timeout = timeout

    async def list_tools(self) -> list[MCPTool]:
        """动态读取 MCP Server 的 Tool Schema，不预先把全部工具注入 Agent。"""
        try:
            async with asyncio.timeout(self.timeout):
                async with streamable_http_client(self.url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        response = await session.list_tools()
                        return [
                            MCPTool(
                                name=tool.name,
                                description=tool.description,
                                input_schema=tool.inputSchema,
                                server=self.server,
                            )
                            for tool in response.tools
                        ]
        except TimeoutError as exc:
            raise MCPError(f"MCP tool discovery timed out: {self.server}") from exc
        except Exception as exc:
            raise MCPError(f"MCP tool discovery failed: {self.server}: {exc}") from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用单个 MCP Tool，并统一转换异常。"""
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.timeout):
                async with streamable_http_client(self.url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments=arguments)
                        return {
                            "server": self.server,
                            "tool": name,
                            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                            "is_error": result.isError,
                            "content": result.content,
                        }
        except TimeoutError as exc:
            raise MCPError(f"MCP tool call timed out: {self.server}/{name}") from exc
        except Exception as exc:
            raise MCPError(f"MCP tool call failed: {self.server}/{name}: {exc}") from exc
