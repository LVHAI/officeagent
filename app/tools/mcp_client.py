from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@dataclass(frozen=True)
class MCPServer:
    name: str
    url: str


class MCPClient:
    def __init__(self, server: MCPServer) -> None:
        self.server = server

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        async with streamable_http_client(self.server.url) as (read, write, _):
            async with ClientSession(read, write) as client:
                await client.initialize()
                yield client

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self.session() as client:
            result = await client.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                    "server": self.server.name,
                }
                for tool in result.tools
            ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        async with self.session() as client:
            return await client.call_tool(name, arguments or {})
