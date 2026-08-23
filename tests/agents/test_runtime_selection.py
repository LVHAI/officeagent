from unittest.mock import patch

from app.agents.deepagents import (
    KNOWLEDGE_PROMPT,
    SUPERVISOR_PROMPT,
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)
from app.agents.knowledge import knowledge_search


def test_supervisor_is_deep_agent_with_three_subagents():
    with patch("app.agents.deepagents.build_chat_model", return_value=object()), patch(
        "app.agents.deepagents.create_deep_agent", return_value="supervisor"
    ) as factory:
        result = create_supervisor()

    assert result == "supervisor"
    kwargs = factory.call_args.kwargs
    assert [item["name"] for item in kwargs["subagents"]] == [
        "knowledge-agent",
        "tool-agent",
        "web-agent",
    ]

    knowledge = kwargs["subagents"][0]
    tool_agent = kwargs["subagents"][1]
    assert knowledge_search in knowledge["tools"]
    assert knowledge["tools"]
    assert all("mcp" not in str(tool).lower() for tool in knowledge["tools"])
    assert tool_agent["tools"]


def test_specialized_agents_use_the_intended_runtime():
    with patch("app.agents.deepagents.build_chat_model", return_value=object()), patch(
        "app.agents.deepagents.create_agent", side_effect=["knowledge", "web", "report"]
    ) as agent_factory, patch(
        "app.agents.deepagents.create_deep_agent", return_value="tool"
    ) as deep_factory:
        assert create_knowledge_agent() == "knowledge"
        assert create_tool_agent() == "tool"
        assert create_web_agent(tools=[]) == "web"
        assert create_report_agent() == "report"

    assert agent_factory.call_count == 3
    assert deep_factory.call_count == 1


def test_prompts_keep_routing_boundaries_explicit():
    assert "MUST delegate to knowledge-agent" in SUPERVISOR_PROMPT
    assert "Knowledge-agent owns the RAG pipeline directly" in SUPERVISOR_PROMPT
    assert "current or external internet information" in SUPERVISOR_PROMPT
    assert "enterprise live/transactional/business data" in SUPERVISOR_PROMPT
    assert "Call the knowledge_search tool" in KNOWLEDGE_PROMPT
    assert "Never call MCP" in KNOWLEDGE_PROMPT
