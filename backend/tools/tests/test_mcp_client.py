"""MCP Client tests for Phase 6."""

import pytest

from backend.tools.mcp_client import MCPClient
from backend.tools.schema import ToolRequest


@pytest.mark.asyncio
async def test_call_tool():
    """验证 MCP Client 可以转换 Tool 请求。"""
    client = MCPClient("http://localhost:9000")

    response = await client.call_tool(
        ToolRequest(
            tool_name="search_customer",
            arguments={"id": 1},
        )
    )

    assert response.success is True
    assert response.data["method"] == "search_customer"
