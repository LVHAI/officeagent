from unittest.mock import patch

from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)


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
