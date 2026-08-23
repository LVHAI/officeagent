from pathlib import Path

import pytest

from app.agents.mcp_client import MCPTool
from app.agents.skills import SkillRegistry, build_skill_runtime_tools, load_skill_metadata


class FakeMCPClient:
    def __init__(self) -> None:
        self.discovery_calls = 0
        self.invocations: list[tuple[str, dict]] = []

    async def discover_tools(self) -> list[MCPTool]:
        self.discovery_calls += 1
        return [
            MCPTool(
                name="sql_query",
                description="Execute a SQL query",
                input_schema={"type": "object", "properties": {"sql": {"type": "string"}}},
            )
        ]

    async def call(self, tool_name: str, arguments: dict):
        self.invocations.append((tool_name, arguments))
        return {"ok": True}


def test_load_skill_metadata_includes_complete_skill_body(tmp_path: Path):
    skill_dir = tmp_path / "crm"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: crm
description: CRM customer analysis
mcp_server: database
mcp_tools:
  - sql_query
---

# CRM Customer Analysis

## Schema guidance

### customer_orders
- `ordered_at`: order time

## Tool policy
- Never invent column names.
""",
        encoding="utf-8",
    )

    registry = load_skill_metadata(tmp_path)
    skill = registry.get("crm")

    assert skill.instructions.startswith("# CRM Customer Analysis")
    assert "ordered_at" in skill.instructions
    assert "Never invent column names" in skill.instructions
    assert "name: crm" not in skill.instructions


@pytest.mark.asyncio
async def test_discovery_returns_skill_instructions_and_caches_mcp_discovery(tmp_path: Path):
    skill_dir = tmp_path / "crm"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: crm
description: CRM customer analysis
mcp_server: database
mcp_tools:
  - sql_query
---

# CRM Customer Analysis

Use `customer_orders.ordered_at`, not `order_date`.
""",
        encoding="utf-8",
    )

    registry = load_skill_metadata(tmp_path)
    client = FakeMCPClient()
    runtime_tools = build_skill_runtime_tools(registry, lambda _: client)
    discover = next(tool for tool in runtime_tools if tool.name == "discover_skill_mcp_tools")

    first = await discover.ainvoke({"skill_name": "crm"})
    second = await discover.ainvoke({"skill_name": "crm"})

    assert first["skill_name"] == "crm"
    assert "customer_orders.ordered_at" in first["instructions"]
    assert first["tools"][0]["name"] == "sql_query"
    assert second["instructions"] == first["instructions"]
    assert client.discovery_calls == 1
