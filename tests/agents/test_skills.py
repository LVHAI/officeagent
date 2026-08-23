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


def test_deepagent_uses_project_skills_for_tool_agent(monkeypatch):
    import app.agents.deepagents as deepagents_module

    captured = {}

    monkeypatch.setattr(deepagents_module, "build_chat_model", lambda: object())
    monkeypatch.setattr(deepagents_module, "build_tavily_search", lambda: None)

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(deepagents_module, "create_deep_agent", fake_create_deep_agent)

    deepagents_module.create_supervisor(tool_tools=[])

    assert captured["skills"] == ["/skills/"]
    tool_agent = next(item for item in captured["subagents"] if item["name"] == "tool-agent")
    assert tool_agent["skills"] == ["/skills/"]
    assert captured["backend"] is not None


def test_project_skills_have_deepagent_frontmatter():
    from pathlib import Path

    expected = {
        "crm": "CRM customer analysis and PostgreSQL access through the Database MCP sql_query tool.",
        "sql": "Generic read-only PostgreSQL analysis through the Database MCP Server.",
        "report": "Executive-ready report aggregation from validated agent outputs.",
    }
    root = Path(__file__).resolve().parents[2]

    for skill_name, description in expected.items():
        content = (root / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert f"name: {skill_name}\n" in content
        assert f"description: {description}\n" in content
        assert "\n---\n" in content
