from unittest.mock import MagicMock

import pytest

from app.agents import deepagents


@pytest.mark.parametrize(
    "factory, expected",
    [
        (deepagents.create_supervisor, "deep"),
        (deepagents.create_tool_agent, "deep"),
        (deepagents.create_knowledge_agent, "standard"),
        (deepagents.create_web_agent, "standard"),
        (deepagents.create_report_agent, "standard"),
    ],
)
def test_agent_factories_use_the_declared_runtime(monkeypatch, factory, expected):
    deep = MagicMock(name="deep_agent")
    standard = MagicMock(name="standard_agent")
    monkeypatch.setattr(deepagents, "create_deep_agent", deep)
    monkeypatch.setattr(deepagents, "create_agent", standard)
    monkeypatch.setattr(deepagents, "build_chat_model", MagicMock())
    monkeypatch.setattr(deepagents, "build_tavily_search", MagicMock(return_value=MagicMock()))

    result = factory()

    expected_factory = deep if expected == "deep" else standard
    assert result is expected_factory.return_value
    expected_factory.assert_called_once()


def test_supervisor_declares_specialist_subagents(monkeypatch):
    deep = MagicMock()
    monkeypatch.setattr(deepagents, "create_deep_agent", deep)
    monkeypatch.setattr(deepagents, "build_chat_model", MagicMock())
    monkeypatch.setattr(deepagents, "build_tavily_search", MagicMock(return_value=MagicMock()))

    deepagents.create_supervisor()

    kwargs = deep.call_args.kwargs
    names = {item["name"] for item in kwargs["subagents"]}
    assert names == {"knowledge-agent", "tool-agent", "web-agent"}
