from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.agents.mcp_client import MCPClient, MCPTool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Skill:
    """Skill metadata plus the complete instructions from SKILL.md."""

    name: str
    description: str
    instructions: str = ""
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
    """Load Skill metadata and the complete SKILL.md body for runtime use."""
    registry = SkillRegistry()
    if not skills_root.exists():
        return registry

    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        frontmatter = _read_frontmatter(skill_file)
        name = str(frontmatter.get("name") or skill_file.parent.name).strip()
        description = str(frontmatter.get("description") or "").strip()
        mcp_server = str(frontmatter.get("mcp_server") or "").strip() or None
        tool_names = tuple(_parse_list(frontmatter.get("mcp_tools", "")))
        instructions = _read_skill_body(skill_file)
        registry.register(
            Skill(
                name=name,
                description=description,
                instructions=instructions,
                tool_names=tool_names,
                mcp_server=mcp_server,
                path=skill_file,
            )
        )
        logger.info(
            "skill.load name=%s path=%s instructions_length=%d mcp_server=%s tools=%s",
            name,
            skill_file,
            len(instructions),
            mcp_server or "-",
            list(tool_names),
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


def _read_skill_body(path: Path) -> str:
    """Read the complete Markdown body after YAML frontmatter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return "\n".join(lines).strip()

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        return "\n".join(lines).strip()
    return "\n".join(lines[closing_index + 1 :]).strip()


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


def _serialize_tool_arguments(arguments: dict[str, Any]) -> str:
    """Serialize tool arguments for logs without failing on non-JSON-native values."""
    try:
        return json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001 - logging must never break tool execution
        return repr(arguments)


async def discover_skill_tools(
    client: MCPClient,
    registry: SkillRegistry,
    skill_name: str,
) -> list[MCPTool]:
    """Dynamically discover one Skill's MCP schema and apply its tool allowlist."""
    skill = registry.get(skill_name)
    if not skill.mcp_server:
        return []
    definitions = await client.discover_tools()
    selected = registry.select_tools(skill_name, definitions)
    logger.info(
        "skill.mcp.discovery skill=%s server=%s discovered=%d selected=%d instructions_length=%d",
        skill.name,
        skill.mcp_server,
        len(definitions),
        len(selected),
        len(skill.instructions),
    )
    return selected


def build_skill_runtime_tools(
    registry: SkillRegistry,
    get_client: Callable[[str], MCPClient],
) -> list[StructuredTool]:
    """Expose Skill runtime operations; concrete MCP tools never enter Agent Context."""

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

    # Runtime tools are created per Tool Agent instance, so this cache is scoped to
    # that agent/request lifecycle rather than shared globally between requests.
    discovered_tools: dict[str, dict[str, MCPTool]] = {}

    async def discover_skill_mcp_tools(skill_name: str) -> dict[str, Any]:
        skill = registry.get(skill_name)
        if not skill.mcp_server:
            logger.info(
                "skill.mcp.discovery.no_server skill=%s instructions_length=%d",
                skill.name,
                len(skill.instructions),
            )
            return {
                "skill_name": skill.name,
                "instructions": skill.instructions,
                "tools": [],
            }

        cached = discovered_tools.get(skill_name)
        if cached is not None:
            logger.info(
                "skill.mcp.discovery.cache_hit skill=%s server=%s selected=%d instructions_length=%d",
                skill.name,
                skill.mcp_server,
                len(cached),
                len(skill.instructions),
            )
            definitions = list(cached.values())
        else:
            client = get_client(skill.mcp_server)
            logger.info(
                "skill.mcp.discovery.start skill=%s server=%s instructions_length=%d",
                skill.name,
                skill.mcp_server,
                len(skill.instructions),
            )
            definitions = await discover_skill_tools(client, registry, skill_name)
            discovered_tools[skill_name] = {definition.name: definition for definition in definitions}
            logger.info(
                "skill.mcp.discovery.completed skill=%s server=%s selected=%d instructions_length=%d",
                skill.name,
                skill.mcp_server,
                len(definitions),
                len(skill.instructions),
            )

        return {
            "skill_name": skill.name,
            "instructions": skill.instructions,
            "tools": [
                {
                    "name": definition.name,
                    "description": definition.description,
                    "input_schema": definition.input_schema,
                }
                for definition in definitions
            ],
        }

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

        definitions = discovered_tools.get(skill_name)
        if definitions is None:
            raise ValueError(
                f"Skill {skill_name!r} has not been discovered; call discover_skill_mcp_tools first"
            )
        definition = definitions.get(tool_name)
        if definition is None:
            raise ValueError(f"MCP tool {tool_name!r} was not discovered for Skill {skill_name!r}")

        client = get_client(skill.mcp_server)
        invocation_id = uuid.uuid4().hex[:12]
        arguments_text = _serialize_tool_arguments(arguments)
        sql = arguments.get("sql") if isinstance(arguments, dict) else None
        started = time.perf_counter()
        logger.info(
            "skill.mcp.invoke.start invocation_id=%s skill=%s server=%s tool=%s arguments=%s sql=%s instructions_length=%d",
            invocation_id,
            skill.name,
            skill.mcp_server,
            definition.name,
            arguments_text,
            sql if sql is not None else "-",
            len(skill.instructions),
        )
        try:
            result = await client.call(definition.name, arguments)
        except Exception:
            logger.exception(
                "skill.mcp.invoke.failed invocation_id=%s skill=%s server=%s tool=%s elapsed_ms=%.1f arguments=%s sql=%s",
                invocation_id,
                skill.name,
                skill.mcp_server,
                definition.name,
                (time.perf_counter() - started) * 1000,
                arguments_text,
                sql if sql is not None else "-",
            )
            raise
        logger.info(
            "skill.mcp.invoke.completed invocation_id=%s skill=%s server=%s tool=%s elapsed_ms=%.1f result_type=%s",
            invocation_id,
            skill.name,
            skill.mcp_server,
            definition.name,
            (time.perf_counter() - started) * 1000,
            type(result).__name__,
        )
        return result

    available_skills = ", ".join(canonical_skills) or "<none>"
    available_tools = ", ".join(authorized_tools) or "<none>"
    return [
        StructuredTool.from_function(
            coroutine=discover_skill_mcp_tools,
            name="discover_skill_mcp_tools",
            description=(
                "Select a registered Skill and discover its authorized MCP tools. "
                "This operation returns the COMPLETE SKILL.md instructions together with "
                "the discovered MCP schemas. You MUST follow the returned Skill instructions "
                "and schema when constructing the next MCP call. "
                f"Canonical Skill names are: {available_skills}. "
                "The Skill name must exactly match a registered Skill; do not invent aliases."
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
                "Call discover_skill_mcp_tools first. The invocation must follow the selected Skill's "
                "returned SKILL.md instructions and discovered schema."
            ),
            args_schema=InvokeArgs,
        ),
    ]


DEFAULT_SKILLS = SkillRegistry()
