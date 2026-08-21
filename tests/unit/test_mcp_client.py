import pytest

from app.mcp.client import MCPClient, MCPError


class FakeClient(MCPClient):
    async def list_tools(self):
        return []


@pytest.mark.asyncio
async def test_mcp_client_timeout_is_configurable():
    client = FakeClient("crm", "http://localhost:8101/mcp", timeout=0.1)
    assert client.server == "crm"
    assert client.timeout == 0.1


def test_mcp_error_is_stable_application_exception():
    error = MCPError("tool failed")
    assert str(error) == "tool failed"
