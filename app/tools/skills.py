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
    def __init__(self, clients: dict[str, MCPClient]) -> None:
        self.clients = clients
        self.skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"name": skill.name, "description": skill.description, "tools": list(skill.tools)}
            for skill in self.skills.values()
        ]

    async def discover_tools(self, skill_name: str) -> list[dict[str, Any]]:
        skill = self.skills[skill_name]
        return await self.clients[skill.server].list_tools()

    async def invoke(self, skill_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        skill = self.skills[skill_name]
        if skill.tools and tool_name not in skill.tools:
            raise ValueError(f"tool {tool_name!r} is not allowed by skill {skill_name!r}")
        return await self.clients[skill.server].call_tool(tool_name, arguments)
