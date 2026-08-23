import app.agents.deepagents as deepagents
from app.agents.planner import create_supervisor


def test_supervisor_factory_has_single_owner():
    assert callable(create_supervisor)
    assert not hasattr(deepagents, "create_supervisor")
