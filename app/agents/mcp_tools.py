from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from app.agents.mcp_client import MCPClient, MCPTool


def build_langchain_tools(client: MCPClient, definitions: list[MCPTool]) -> list[StructuredTool]:
    """把 MCP Schema 转成 LangChain Tool，仅向 Tool Agent 注入 Skill 允许的工具。"""
    result: list[StructuredTool] = []
    for definition in definitions:
        async def invoke(arguments: dict[str, Any], name: str = definition.name):
            return await client.call(name, arguments)

        result.append(
            StructuredTool.from_function(
                coroutine=invoke,
                name=definition.name.replace(".", "_"),
                description=definition.description or f"MCP tool: {definition.name}",
                args_schema=None,
            )
        )
    return result
