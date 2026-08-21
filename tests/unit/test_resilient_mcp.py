import asyncio

import pytest

from app.mcp.client import MCPError
from app.mcp.resilient_client import CircuitBreaker, CircuitOpenError, ResilientMCPClient


class FakeClient:
    server = "crm"

    def __init__(self, failures: int = 0):
        self.failures = failures
        self.calls = 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        if self.calls <= self.failures:
            raise MCPError("temporary failure")
        return {"tool": name}

    async def list_tools(self):
        return []


@pytest.mark.asyncio
async def test_mcp_retries_with_bounded_attempts():
    client = FakeClient(failures=2)
    resilient = ResilientMCPClient(client, max_retries=2, base_delay=0, max_delay=0)

    result = await resilient.call_tool("query", {})

    assert result == {"tool": "query"}
    assert client.calls == 3


@pytest.mark.asyncio
async def test_mcp_cancellation_is_not_retried():
    client = FakeClient()

    async def cancelled(*_):
        raise asyncio.CancelledError

    client.call_tool = cancelled
    resilient = ResilientMCPClient(client, max_retries=2, base_delay=0, max_delay=0)

    with pytest.raises(asyncio.CancelledError):
        await resilient.call_tool("query", {})
    assert client.calls == 0


@pytest.mark.asyncio
async def test_mcp_circuit_opens_after_failures():
    client = FakeClient(failures=10)
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    resilient = ResilientMCPClient(client, max_retries=0, breaker=breaker)

    with pytest.raises(MCPError):
        await resilient.call_tool("query", {})
    with pytest.raises(MCPError):
        await resilient.call_tool("query", {})
    with pytest.raises(CircuitOpenError):
        await resilient.call_tool("query", {})
