from unittest.mock import patch

from app.agents.deepagents import (
    KNOWLEDGE_PROMPT,
    TOOL_PROMPT,
    create_knowledge_agent,
    create_report_agent,
    create_tool_agent,
    create_web_agent,
)
from app.agents.knowledge import knowledge_search
from app.agents.planner import PLANNER_PROMPT, create_supervisor


def test_supervisor_is_owned_by_planner_and_has_no_child_agent_tools():
    with patch("app.agents.planner.build_chat_model", return_value=object()), patch(
        "app.agents.planner.create_deep_agent", return_value="supervisor"
    ) as factory:
        result = create_supervisor()

    assert result._agent == "supervisor"
    kwargs = factory.call_args.kwargs
    assert kwargs["tools"]
    assert [tool.name for tool in kwargs["tools"]] == ["submit_execution_plan"]
    assert "subagents" not in kwargs


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
    assert "sole planning and delegation decision center" in PLANNER_PROMPT
    assert "Knowledge Agent owns the RAG pipeline directly" in PLANNER_PROMPT
    assert "The Tool Agent decides Skill -> MCP internally" in PLANNER_PROMPT
    assert "Call the knowledge_search tool" in KNOWLEDGE_PROMPT
    assert "Never call MCP" in KNOWLEDGE_PROMPT
    assert "discover_skill_mcp_tools" in TOOL_PROMPT
    assert "invoke_skill_mcp_tool" in TOOL_PROMPT


def test_knowledge_agent_receives_only_the_rag_tool():
    with patch("app.agents.deepagents.build_chat_model", return_value=object()), patch(
        "app.agents.deepagents.create_agent", return_value="knowledge"
    ) as factory:
        assert create_knowledge_agent() == "knowledge"

    kwargs = factory.call_args.kwargs
    assert kwargs["tools"] == [knowledge_search]
