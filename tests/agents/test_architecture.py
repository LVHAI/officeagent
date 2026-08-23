from app.agents import deepagents, planner


def test_supervisor_ownership_is_exclusive_to_planner():
    assert callable(planner.create_supervisor)
    assert not hasattr(deepagents, "create_supervisor")


def test_specialist_factories_are_separate_from_supervisor():
    assert callable(deepagents.create_knowledge_agent)
    assert callable(deepagents.create_tool_agent)
    assert callable(deepagents.create_web_agent)
    assert callable(deepagents.create_report_agent)
