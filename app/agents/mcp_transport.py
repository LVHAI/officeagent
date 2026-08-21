from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def streamable_http_transport(url: str) -> AsyncIterator[Any]:
    """连接 Docker 中的 Streamable HTTP MCP Server；Session 生命周期由调用方控制。"""
    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session
