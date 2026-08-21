import pytest

from app.agents.mcp_client import MCPTool
from app.agents.skills import Skill, SkillRegistry


def test_skill_registry_loads_only_allowed_tools():
    registry = SkillRegistry([Skill("crm", "CRM operations", ("customer.search",))])
    tools = [
        MCPTool("customer.search", "查询客户", {}),
        MCPTool("database.query", "查询数据库", {}),
    ]

    selected = registry.select_tools("crm", tools)

    assert [tool.name for tool in selected] == ["customer.search"]


def test_unknown_skill_is_rejected():
    with pytest.raises(KeyError):
        SkillRegistry().get("missing")
