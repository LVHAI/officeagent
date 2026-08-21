from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.retry import retry_async


@dataclass(frozen=True)
class MCPServer:
    name: str
    url: str
    timeout_seconds: float = 15.0


class MCPClient:
    def __init__(self, server: MCPServer) -> None:
        self.server = server

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        async with streamable_http_client(self.server.url) as (read, write, _):
            async with ClientSession(read, write) as client:
                await retry_async(
                    lambda: asyncio.wait_for(client.initialize(), timeout=self.server.timeout_seconds),
                    retries=2,
                )
                yield client

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self.session() as client:
            result = await retry_async(
                lambda: asyncio.wait_for(client.list_tools(), timeout=self.server.timeout_seconds),
                retries=2,
            )
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
            return await retry_async(
                lambda: asyncio.wait_for(
                    client.call_tool(name, arguments or {}),
                    timeout=self.server.timeout_seconds,
                ),
                retries=2,
            )
