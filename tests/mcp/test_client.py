import asyncio

import pytest

from app.mcp.client import MCPClient, MCPError, MCPToolResult


def test_mcp_tool_result_contract():
    result = MCPToolResult(
        server="crm",
        tool="customer.query",
        content={"id": 1},
        is_error=False,
        elapsed_ms=1.2,
    )
    assert result.server == "crm"
    assert result.tool == "customer.query"
    assert result.is_error is False


@pytest.mark.asyncio
async def test_mcp_discovery_normalizes_timeout(monkeypatch):
    async def timeout(*args, **kwargs):
        raise TimeoutError("boom")

    monkeypatch.setattr("app.mcp.client.asyncio.timeout", timeout)
    client = MCPClient("crm", "http://crm", timeout=0.01)
    with pytest.raises(MCPError, match="discovery timed out"):
        await client.list_tools()


@pytest.mark.asyncio
async def test_mcp_cancellation_is_not_wrapped(monkeypatch):
    class CancelContext:
        async def __aenter__(self):
            raise asyncio.CancelledError

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.mcp.client.asyncio.timeout", lambda *a, **k: CancelContext())
    client = MCPClient("crm", "http://crm")
    with pytest.raises(asyncio.CancelledError):
        await client.list_tools()
