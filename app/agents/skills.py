from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.mcp_client import MCPClient, MCPTool


@dataclass(frozen=True)
class Skill:
    """Skill 元数据；只描述能力边界，不把所有 MCP Schema 注入 Agent Context。"""

    name: str
    description: str
    tool_names: tuple[str, ...] = ()


class SkillRegistry:
    def __init__(self, skills: list[Skill] | None = None) -> None:
        self._skills = {skill.name: skill for skill in skills or []}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {name}") from exc

    def select_tools(self, skill_name: str, tools: list[MCPTool]) -> list[MCPTool]:
        skill = self.get(skill_name)
        allowed = set(skill.tool_names)
        return [tool for tool in tools if tool.name in allowed]


async def discover_skill_tools(
    client: MCPClient,
    registry: SkillRegistry,
    skill_name: str,
) -> list[MCPTool]:
    """动态发现 MCP Schema，并只返回当前 Skill 允许使用的工具。"""
    return registry.select_tools(skill_name, await client.discover_tools())
