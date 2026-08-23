from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.agents.mcp_client import MCPClient, MCPTool


@dataclass(frozen=True)
class Skill:
    """Skill 元数据；只描述能力边界，不把 MCP Schema 注入 Agent Context。"""

    name: str
    description: str
    tool_names: tuple[str, ...] = ()
    mcp_server: str | None = None
    path: Path | None = None


class SkillRegistry:
    def __init__(self, skills: list[Skill] | None = None) -> None:
        self._skills = {skill.name: skill for skill in skills or []}

    def register(self, skill: Skill) -> None:
        if not skill.name:
            raise ValueError("Skill name must not be empty")
        if skill.name in self._skills:
            raise ValueError(f"Duplicate skill name: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._skills)) or "<none>"
            raise KeyError(f"Unknown skill: {name}; available skills: {available}") from exc

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def canonical_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))

    def authorized_tool_names(self) -> tuple[str, ...]:
        return tuple(sorted({name for skill in self._skills.values() for name in skill.tool_names}))

    def select_tools(self, skill_name: str, tools: list[MCPTool]) -> list[MCPTool]:
        allowed = set(self.get(skill_name).tool_names)
        return [tool for tool in tools if tool.name in allowed]

    def route(self, task: str) -> list[Skill]:
        """提供轻量候选筛选；最终 Skill 选择由 Tool Agent 完成。"""
        text = task.lower()
        matches: list[Skill] = []
        for skill in self._skills.values():
            tokens = {skill.name.lower(), *skill.description.lower().split()}
            if any(token in text for token in tokens if len(token) > 2):
                matches.append(skill)
        return matches


def load_skill_metadata(skills_root: Path) -> SkillRegistry:
    """只加载轻量 metadata；完整 SKILL.md 由 Tool Agent 按需读取。"""
    registry = SkillRegistry()
    if not skills_root.exists():
        return registry

    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        frontmatter = _read_frontmatter(skill_file)
        name = str(frontmatter.get("name") or skill_file.parent.name).strip()
        description = str(frontmatter.get("description") or "").strip()
        mcp_server = str(frontmatter.get("mcp_server") or "").strip() or None
        tool_names = tuple(_parse_list(frontmatter.get("mcp_tools", "")))
        registry.register(
            Skill(
                name=name,
                description=description,
                tool_names=tool_names,
                mcp_server=mcp_server,
                path=skill_file,
            )
        )
    return registry


def _read_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    result: dict[str, str] = {}
    current_list_key: str | None = None
    list_values: dict[str, list[str]] = {}

    for line in lines[1:]:
        if line.strip() == "---":
            break
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            list_values.setdefault(current_list_key, []).append(stripped[2:].strip().strip("'\""))
            continue
        if ":" not in line or line.startswith(" "):
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        result[key] = value
        current_list_key = key if not value else None

    for key, values in list_values.items():
        result[key] = ",".join(values)
    return result


def _parse_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip().strip("'\"") for item in value.split(",") if item.strip()]


def _literal_type(values: tuple[str, ...]) -> Any:
    """Build a Pydantic-compatible Literal type from registry values."""
    if not values:
        return str
    return Literal.__getitem__(values)


async def discover_skill_tools(
    client: MCPClient,
    registry: SkillRegistry,
    skill_name: str,
) -> list[MCPTool]:
    """动态发现一个 Skill 对应的 MCP Schema，并执行 Skill 白名单过滤。"""
    skill = registry.get(skill_name)
    if not skill.mcp_server:
        return []
    definitions = await client.discover_tools()
    selected = registry.select_tools(skill_name, definitions)
    logger = __import__("logging").getLogger(__name__)
    logger.info(
        "skill.mcp.discovery skill=%s server=%s discovered=%d selected=%d",
        skill.name,
        skill.mcp_server,
        len(definitions),
        len(selected),
    )
    return selected


def build_skill_runtime_tools(
    registry: SkillRegistry,
    get_client: Callable[[str], MCPClient],
) -> list[StructuredTool]:
    """Only expose Skill runtime operations; concrete MCP tools never enter Agent Context."""

    canonical_skills = registry.canonical_names()
    authorized_tools = registry.authorized_tool_names()
    skill_type = _literal_type(canonical_skills)
    tool_type = _literal_type(authorized_tools)

    DiscoverArgs = create_model("DiscoverSkillMCPToolsArgs", skill_name=(skill_type, ...))
    InvokeArgs = create_model(
        "InvokeSkillMCPToolArgs",
        skill_name=(skill_type, ...),
        tool_name=(tool_type, ...),
        arguments=(dict[str, Any], ...),
    )

    async def discover_skill_mcp_tools(skill_name: str) -> list[dict[str, Any]]:
        skill = registry.get(skill_name)
        if not skill.mcp_server:
            return []
        client = get_client(skill.mcp_server)
        definitions = await discover_skill_tools(client, registry, skill_name)
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.input_schema,
            }
            for definition in definitions
        ]

    async def invoke_skill_mcp_tool(
        skill_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        skill = registry.get(skill_name)
        if not skill.mcp_server:
            raise ValueError(f"Skill {skill_name!r} has no MCP server mapping")
        if tool_name not in skill.tool_names:
            raise ValueError(f"Tool {tool_name!r} is not allowed by Skill {skill_name!r}")

        client = get_client(skill.mcp_server)
        definitions = await discover_skill_tools(client, registry, skill_name)
        definition_names = {definition.name for definition in definitions}
        if tool_name not in definition_names:
            raise ValueError(f"MCP tool {tool_name!r} was not discovered for Skill {skill_name!r}")

        return await client.call(tool_name, arguments)

    available_skills = ", ".join(canonical_skills) or "<none>"
    available_tools = ", ".join(authorized_tools) or "<none>"
    return [
        StructuredTool.from_function(
            coroutine=discover_skill_mcp_tools,
            name="discover_skill_mcp_tools",
            description=(
                "Discover MCP tool schemas only for the selected Skill. "
                f"Canonical Skill names are: {available_skills}. "
                "The Skill name must exactly match a registered Skill; do not invent aliases. "
                "Select a Skill first and call this before MCP invocation."
            ),
            args_schema=DiscoverArgs,
        ),
        StructuredTool.from_function(
            coroutine=invoke_skill_mcp_tool,
            name="invoke_skill_mcp_tool",
            description=(
                "Invoke one MCP tool explicitly authorized by the selected Skill. "
                f"Canonical Skill names are: {available_skills}. "
                f"Authorized MCP tool names are: {available_tools}. "
                "The Skill name and tool name must exactly match registered values; do not invent names. "
                "Call discover_skill_mcp_tools first and invoke only a discovered, Skill-authorized tool."
            ),
            args_schema=InvokeArgs,
        ),
    ]


DEFAULT_SKILLS = SkillRegistry()
