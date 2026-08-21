from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from app.tools.mcp_client import MCPClient


def _args_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """把 MCP JSON Schema 转成 LangChain/Pydantic 参数模型。"""
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, definition in properties.items():
        field_type: Any = str
        field_type_name = definition.get("type") if isinstance(definition, dict) else None
        if field_type_name == "integer":
            field_type = int
        elif field_type_name == "number":
            field_type = float
        elif field_type_name == "boolean":
            field_type = bool
        default = ... if field_name in required else None
        fields[field_name] = (field_type, default)
    return create_model(name, **fields)


async def discover_langchain_tools(client: MCPClient, skill_name: str) -> list[StructuredTool]:
    """动态发现 MCP Tool，并转换成 DeepAgents 可直接调用的 LangChain Tool。"""
    discovered = await client.list_tools()
    tools: list[StructuredTool] = []
    for item in discovered:
        tool_name = str(item["name"])
        description = str(item.get("description") or f"MCP tool: {tool_name}")
        args_schema = _args_model(
            f"{skill_name}_{tool_name}_Args",
            item.get("input_schema", {}),
        )

        async def invoke(arguments: dict[str, Any], *, _name: str = tool_name) -> Any:
            return await client.call_tool(_name, arguments)

        tools.append(
            StructuredTool.from_function(
                coroutine=invoke,
                name=f"{skill_name}_{tool_name}",
                description=description,
                args_schema=args_schema,
            )
        )
    return tools
