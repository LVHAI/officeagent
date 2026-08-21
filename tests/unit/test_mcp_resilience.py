import pytest

from app.tools.mcp_client import CircuitOpenError, MCPClient, MCPServer


@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_failures() -> None:
    client = MCPClient(MCPServer("crm", "http://localhost:1", failure_threshold=2))

    await client._record_failure()
    await client._record_failure()

    with pytest.raises(CircuitOpenError):
        await client._before_call()


@pytest.mark.asyncio
async def test_circuit_resets_after_success() -> None:
    client = MCPClient(MCPServer("crm", "http://localhost:1", failure_threshold=2))
    await client._record_failure()
    await client._record_success()

    await client._before_call()
