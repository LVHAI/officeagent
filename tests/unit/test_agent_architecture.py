from unittest.mock import MagicMock

import pytest

from app.agents import deepagents, planner


@pytest.mark.parametrize(
    "factory, expected",
    [
        (deepagents.create_tool_agent, "deep"),
        (deepagents.create_knowledge_agent, "standard"),
        (deepagents.create_web_agent, "standard"),
    ],
)
def test_specialist_factories_use_the_declared_runtime(monkeypatch, factory, expected):
    deep = MagicMock(name="deep_agent")
    standard = MagicMock(name="standard_agent")
    monkeypatch.setattr(deepagents, "create_deep_agent", deep)
    monkeypatch.setattr(deepagents, "create_agent", standard)
    monkeypatch.setattr(deepagents, "build_chat_model", MagicMock())
    monkeypatch.setattr(
        deepagents,
        "build_tavily_search",
        MagicMock(return_value=MagicMock()),
    )

    result = factory()

    expected_factory = deep if expected == "deep" else standard
    assert result is expected_factory.return_value
    expected_factory.assert_called_once()


def test_report_agent_uses_the_report_adapter(monkeypatch):
    model = MagicMock(name="chat_model")
    monkeypatch.setattr(deepagents, "build_chat_model", MagicMock(return_value=model))

    result = deepagents.create_report_agent()

    assert isinstance(result, deepagents._ReportAgent)
    assert result._model is model
    model.bind_tools.assert_called_once()


def test_supervisor_is_owned_by_planner_and_exposes_only_plan_tool(monkeypatch):
    deep = MagicMock(name="deep_agent")
    model = MagicMock(name="chat_model")
    monkeypatch.setattr(planner, "create_deep_agent", deep)
    monkeypatch.setattr(planner, "build_chat_model", MagicMock(return_value=model))

    result = planner.create_supervisor()

    assert result._agent is deep.return_value
    deep.assert_called_once()
    kwargs = deep.call_args.kwargs
    assert kwargs["model"] is model
    assert kwargs["tools"] == [planner.PLAN_TOOL]
    assert "subagents" not in kwargs
    assert "MCP" in kwargs["system_prompt"]
    assert "submit_execution_plan" in kwargs["system_prompt"]


def test_supervisor_factory_alias_points_to_the_canonical_planner_factory(monkeypatch):
    supervisor = MagicMock(name="supervisor")
    monkeypatch.setattr(planner, "create_supervisor", MagicMock(return_value=supervisor))

    assert planner.create_execution_planner() is supervisor
    planner.create_supervisor.assert_called_once()
