from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.tools.mcp_client import MCPClient


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    server: str
    tools: tuple[str, ...] = field(default_factory=tuple)


class SkillRegistry:
    """Skill 注册中心：按需发现 MCP Tool，避免把全部 Tool Schema 注入 Agent Context。"""

    def __init__(self, clients: dict[str, MCPClient]) -> None:
        self.clients = clients
        self.skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "server": skill.server,
                "tools": list(skill.tools),
            }
            for skill in self.skills.values()
        ]

    def get(self, skill_name: str) -> Skill:
        try:
            return self.skills[skill_name]
        except KeyError as exc:
            raise KeyError(f"skill {skill_name!r} is not registered") from exc

    async def discover_tools(self, skill_name: str) -> list[dict[str, Any]]:
        skill = self.get(skill_name)
        tools = await self.clients[skill.server].list_tools()
        # 只暴露 Skill 声明允许使用的工具，防止越权调用 MCP Tool。
        if skill.tools:
            return [tool for tool in tools if tool["name"] in skill.tools]
        return tools

    async def invoke(self, skill_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        skill = self.get(skill_name)
        if skill.tools and tool_name not in skill.tools:
            raise ValueError(f"tool {tool_name!r} is not allowed by skill {skill_name!r}")
        return await self.clients[skill.server].call_tool(tool_name, arguments)
