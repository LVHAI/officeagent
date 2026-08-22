import pytest

from app.agents.mcp_client import MCPTool
from app.agents.mcp_registry import build_langchain_tools


class FakeClient:
    async def call(self, name, arguments):
        return {"tool": name, "arguments": arguments}


@pytest.mark.asyncio
async def test_build_langchain_tools_preserves_mcp_input_schema():
    definitions = [
        MCPTool(
            name="customer.query",
            description="查询客户",
            input_schema={
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "required": ["region"],
            },
        )
    ]

    tool = build_langchain_tools(FakeClient(), definitions)[0]

    assert tool.name == "customer_query"
    assert "region" in tool.args_schema.model_fields
    result = await tool.ainvoke({"region": "East China"})
    assert result["tool"] == "customer.query"
    assert result["arguments"] == {"region": "East China"}
