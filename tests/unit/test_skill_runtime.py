from __future__ import annotations

import pytest

from app.agents.mcp_client import MCPTool
from app.agents.skills import Skill, SkillRegistry, build_skill_runtime_tools


class FakeMCPClient:
    def __init__(self) -> None:
        self.discover_calls = 0
        self.invoke_calls = []

    async def discover_tools(self) -> list[MCPTool]:
        self.discover_calls += 1
        return [MCPTool(name="sql_query", description="query", input_schema={})]

    async def call(self, tool_name: str, arguments: dict):
        self.invoke_calls.append((tool_name, arguments))
        return {"ok": True}


def make_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            Skill(
                name="crm",
                description="CRM customer and sales data",
                tool_names=("sql_query",),
                mcp_server="database",
            )
        ]
    )


@pytest.mark.asyncio
async def test_invoke_auto_discovers_when_model_skips_discovery() -> None:
    client = FakeMCPClient()
    tools = build_skill_runtime_tools(make_registry(), lambda _: client)
    invoke = next(tool for tool in tools if tool.name == "invoke_skill_mcp_tool")

    result = await invoke.ainvoke(
        {
            "skill_name": "crm",
            "tool_name": "sql_query",
            "arguments": {"value": "C001"},
        }
    )

    assert result == {"ok": True}
    assert client.discover_calls == 1
    assert client.invoke_calls == [("sql_query", {"value": "C001"})]


@pytest.mark.asyncio
async def test_second_runtime_can_invoke_without_discovery() -> None:
    first_client = FakeMCPClient()
    first_tools = build_skill_runtime_tools(make_registry(), lambda _: first_client)
    first_invoke = next(tool for tool in first_tools if tool.name == "invoke_skill_mcp_tool")
    await first_invoke.ainvoke(
        {
            "skill_name": "crm",
            "tool_name": "sql_query",
            "arguments": {"value": "C001"},
        }
    )

    second_client = FakeMCPClient()
    second_tools = build_skill_runtime_tools(make_registry(), lambda _: second_client)
    second_invoke = next(tool for tool in second_tools if tool.name == "invoke_skill_mcp_tool")
    await second_invoke.ainvoke(
        {
            "skill_name": "crm",
            "tool_name": "sql_query",
            "arguments": {"value": "C001"},
        }
    )

    assert first_client.discover_calls == 1
    assert second_client.discover_calls == 1
    assert len(first_client.invoke_calls) == 1
    assert len(second_client.invoke_calls) == 1
