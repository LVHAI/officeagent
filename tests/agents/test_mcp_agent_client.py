import pytest

from app.agents.mcp_client import MCPClient, MCPError


class FakeTool:
    name = "customer.search"
    description = "查询客户"
    inputSchema = {"type": "object", "properties": {"name": {"type": "string"}}}


class FakeResponse:
    tools = [FakeTool()]


class FakeTransport:
    async def list_tools(self):
        return FakeResponse()

    async def call_tool(self, name, arguments):
        return {"name": name, "arguments": arguments}


class FailingTransport:
    async def list_tools(self):
        raise RuntimeError("connection refused")

    async def call_tool(self, name, arguments):
        raise RuntimeError("timeout")


class TaskGroupFailingTransport:
    async def list_tools(self):
        raise ExceptionGroup("unhandled errors in a TaskGroup", [ConnectionError("connection refused")])

    async def call_tool(self, name, arguments):
        raise ExceptionGroup("unhandled errors in a TaskGroup", [ConnectionError("connection refused")])


@pytest.mark.asyncio
async def test_mcp_client_discovers_tool_schema_and_invokes_tool():
    client = MCPClient(FakeTransport())

    tools = await client.discover_tools()
    result = await client.call("customer.search", {"name": "Alice"})

    assert tools[0].name == "customer.search"
    assert tools[0].input_schema["properties"]["name"]["type"] == "string"
    assert result["name"] == "customer.search"


@pytest.mark.asyncio
async def test_mcp_client_normalizes_transport_errors():
    client = MCPClient(FailingTransport())

    with pytest.raises(MCPError, match="discovery"):
        await client.discover_tools()

    with pytest.raises(MCPError, match="invocation"):
        await client.call("customer.search", {})


@pytest.mark.asyncio
async def test_mcp_client_exposes_nested_taskgroup_error_details():
    client = MCPClient(TaskGroupFailingTransport(), retry_attempts=1)

    with pytest.raises(MCPError, match="ConnectionError: connection refused"):
        await client.discover_tools()

    with pytest.raises(MCPError, match="ConnectionError: connection refused"):
        await client.call("customer.search", {})
