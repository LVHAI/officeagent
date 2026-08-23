import pytest

from app.agents.mcp_client import MCPTool
from app.agents.skills import Skill, SkillRegistry, build_skill_runtime_tools, load_skill_metadata


def test_skill_registry_loads_only_allowed_tools():
    registry = SkillRegistry([Skill("crm", "CRM operations", ("customer.search",))])
    tools = [
        MCPTool("customer.search", "查询客户", {}),
        MCPTool("database.query", "查询数据库", {}),
    ]

    selected = registry.select_tools("crm", tools)

    assert [tool.name for tool in selected] == ["customer.search"]


def test_unknown_skill_is_rejected():
    with pytest.raises(KeyError, match="available skills"):
        SkillRegistry([Skill("crm", "CRM operations")]).get("missing")


def test_skill_ids_are_exactly_the_registered_ids():
    registry = SkillRegistry([Skill("crm", "CRM operations")])

    assert registry.get("crm").name == "crm"

    for invalid_name in ("crm_skill", "crm_customer_info_skill"):
        with pytest.raises(KeyError, match="available skills"):
            registry.get(invalid_name)


def test_skill_registration_rejects_duplicate_names():
    registry = SkillRegistry([Skill("crm", "CRM operations")])

    with pytest.raises(ValueError, match="Duplicate skill name"):
        registry.register(Skill("crm", "Duplicate CRM"))


def test_skill_metadata_contains_explicit_mcp_boundary():
    from pathlib import Path

    registry = load_skill_metadata(Path(__file__).resolve().parents[2] / "skills")
    crm = registry.get("crm")
    sql = registry.get("sql")

    assert crm.mcp_server == "database"
    assert crm.tool_names == ("sql_query",)
    assert sql.mcp_server == "database"
    assert sql.tool_names == ("sql_query",)


def test_tool_runtime_exposes_only_skill_operations():
    registry = SkillRegistry([
        Skill("crm", "CRM operations", ("sql_query",), "database"),
    ])

    runtime_tools = build_skill_runtime_tools(registry, lambda _: object())

    assert [tool.name for tool in runtime_tools] == [
        "discover_skill_mcp_tools",
        "invoke_skill_mcp_tool",
    ]
    assert all(tool.name != "sql_query" for tool in runtime_tools)
    assert all("crm" in tool.description for tool in runtime_tools)


def test_runtime_tool_schema_only_allows_registered_skill_and_mcp_names():
    registry = SkillRegistry([
        Skill("crm", "CRM operations", ("sql_query",), "database"),
        Skill("sql", "SQL operations", ("sql_query",), "database"),
    ])

    runtime_tools = build_skill_runtime_tools(registry, lambda _: object())
    discover_tool, invoke_tool = runtime_tools
    discover_schema = discover_tool.args_schema.model_json_schema()
    invoke_schema = invoke_tool.args_schema.model_json_schema()

    assert discover_schema["properties"]["skill_name"]["enum"] == ["crm", "sql"]
    assert invoke_schema["properties"]["skill_name"]["enum"] == ["crm", "sql"]
    assert invoke_schema["properties"]["tool_name"]["enum"] == ["sql_query"]
    assert "get_customer_purchases" not in invoke_schema["properties"]["tool_name"]["enum"]


@pytest.mark.asyncio
async def test_runtime_discovers_once_and_reuses_definition_for_invoke():
    class FakeClient:
        def __init__(self):
            self.discover_calls = 0
            self.call_args = []

        async def discover_tools(self):
            self.discover_calls += 1
            return [MCPTool("sql_query", "执行 SQL", {"type": "object"})]

        async def call(self, name, arguments):
            self.call_args.append((name, arguments))
            return {"rows": [{"id": 1}]}

    client = FakeClient()
    registry = SkillRegistry([
        Skill("crm", "CRM operations", ("sql_query",), "database"),
    ])
    runtime_tools = build_skill_runtime_tools(registry, lambda _: client)
    discover_tool, invoke_tool = runtime_tools

    discovered = await discover_tool.ainvoke({"skill_name": "crm"})
    result = await invoke_tool.ainvoke(
        {
            "skill_name": "crm",
            "tool_name": "sql_query",
            "arguments": {"sql": "SELECT 1"},
        }
    )

    assert discovered[0]["name"] == "sql_query"
    assert result == {"rows": [{"id": 1}]}
    assert client.discover_calls == 1
    assert client.call_args == [("sql_query", {"sql": "SELECT 1"})]


@pytest.mark.asyncio
async def test_runtime_repeated_discovery_uses_cached_definitions():
    class FakeClient:
        def __init__(self):
            self.discover_calls = 0

        async def discover_tools(self):
            self.discover_calls += 1
            return [MCPTool("sql_query", "执行 SQL", {"type": "object"})]

        async def call(self, name, arguments):
            return {"ok": True}

    client = FakeClient()
    registry = SkillRegistry([
        Skill("crm", "CRM operations", ("sql_query",), "database"),
    ])
    discover_tool, _ = build_skill_runtime_tools(registry, lambda _: client)

    await discover_tool.ainvoke({"skill_name": "crm"})
    await discover_tool.ainvoke({"skill_name": "crm"})
    await discover_tool.ainvoke({"skill_name": "crm"})

    assert client.discover_calls == 1


@pytest.mark.asyncio
async def test_invoke_requires_discovery_first():
    class FakeClient:
        async def discover_tools(self):
            raise AssertionError("discovery should not happen during invoke")

        async def call(self, name, arguments):
            raise AssertionError("call should not happen without discovery")

    registry = SkillRegistry([
        Skill("crm", "CRM operations", ("sql_query",), "database"),
    ])
    _, invoke_tool = build_skill_runtime_tools(registry, lambda _: FakeClient())

    with pytest.raises(ValueError, match="has not been discovered"):
        await invoke_tool.ainvoke(
            {
                "skill_name": "crm",
                "tool_name": "sql_query",
                "arguments": {"sql": "SELECT 1"},
            }
        )


def test_deepagent_does_not_receive_concrete_mcp_tools(monkeypatch):
    import app.agents.deepagents as deepagents_module

    captured = {}

    monkeypatch.setattr(deepagents_module, "build_chat_model", lambda: object())
    monkeypatch.setattr(deepagents_module, "build_tavily_search", lambda: None)
    monkeypatch.setattr(deepagents_module.mcp_registry, "get_client", lambda _: object())

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(deepagents_module, "create_deep_agent", fake_create_deep_agent)

    deepagents_module.create_supervisor(
        tool_tools=[
            MCPTool("customer_query", "查询客户", {}),
            MCPTool("sql_query", "执行 SQL", {}),
            MCPTool("report_generate", "生成报告", {}),
        ]
    )

    tool_agent = next(item for item in captured["subagents"] if item["name"] == "tool-agent")
    assert tool_agent["skills"] == ["/skills/"]
    assert [tool.name for tool in tool_agent["tools"]] == [
        "discover_skill_mcp_tools",
        "invoke_skill_mcp_tool",
    ]


def test_supervisor_routes_enterprise_data_to_tool_agent():
    import app.agents.deepagents as deepagents_module

    prompt = deepagents_module.SUPERVISOR_PROMPT.lower()
    assert "enterprise live/transactional/business data queries must delegate to tool-agent" in prompt
    assert "knowledge-agent is only for enterprise documents/knowledge/rag content" in prompt


def test_tool_agent_requires_skill_before_mcp():
    import app.agents.deepagents as deepagents_module

    prompt = deepagents_module.TOOL_PROMPT.lower()
    assert "select exactly the skill" in prompt
    assert "discover_skill_mcp_tools" in prompt
    assert "invoke_skill_mcp_tool" in prompt
    assert "not registered in your agent context" in prompt


def test_project_skills_have_valid_frontmatter():
    from pathlib import Path

    expected = {
        "crm": "CRM customer analysis and PostgreSQL access through the Database MCP sql_query tool.",
        "sql": "Generic read-only PostgreSQL analysis through the Database MCP Server.",
    }
    root = Path(__file__).resolve().parents[2]

    for skill_name, description in expected.items():
        content = (root / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert f"name: {skill_name}\n" in content
        assert f"description: {description}\n" in content
        assert "mcp_server: database\n" in content
        assert "  - sql_query\n" in content
        assert "\n---\n" in content
