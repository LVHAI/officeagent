from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.mcp_client import MCPClient, MCPTool


@dataclass(frozen=True)
class Skill:
    """Skill 元数据；只描述能力边界，不把全部 MCP Schema 注入 Context。"""

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
        allowed = set(self.get(skill_name).tool_names)
        return [tool for tool in tools if tool.name in allowed]

    def route(self, task: str) -> list[Skill]:
        """轻量 Skill Router；生产环境可替换为模型分类器，但仍受 Registry 白名单约束。"""
        text = task.lower()
        matches = []
        for skill in self._skills.values():
            keywords = {skill.name.lower(), *skill.description.lower().split()}
            if any(keyword in text for keyword in keywords if len(keyword) > 2):
                matches.append(skill)
        return matches


DEFAULT_SKILLS = SkillRegistry(
    [
        Skill("sales", "销售 客户 CRM ERP", ("customer_query", "sales_summary")),
        Skill("knowledge", "知识库 文档 Knowledge", ("knowledge_search",)),
        Skill("report", "报告 Report", ("report_generate",)),
    ]
)


async def discover_skill_tools(
    client: MCPClient,
    registry: SkillRegistry,
    skill_name: str,
) -> list[MCPTool]:
    """动态发现 MCP Schema，并只返回当前 Skill 允许使用的工具。"""
    return registry.select_tools(skill_name, await client.discover_tools())
