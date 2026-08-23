from app.agents.graph import _has_execution_plan, _route_after_replan, _route_after_supervisor


def test_missing_execution_plan_routes_to_report():
    state = {"task_id": "t1", "status": "partial"}
    assert _has_execution_plan(state) is False
    assert _route_after_supervisor(state) == "report"


def test_invalid_execution_plan_routes_to_report():
    state = {
        "task_id": "t1",
        "execution_plan": {"rationale": "planner failed"},
        "status": "partial",
    }
    assert _has_execution_plan(state) is False
    assert _route_after_supervisor(state) == "report"
    assert _route_after_replan(state) == "report"


def test_valid_execution_plan_routes_to_execute():
    state = {
        "task_id": "t1",
        "execution_plan": {
            "tasks": [
                {
                    "task_id": "task-1",
                    "agent": "tool-agent",
                    "query": "查询客户 C001",
                    "parallel_group": "default",
                    "depends_on": [],
                    "constraints": {},
                }
            ],
            "rationale": "enterprise data",
        },
        "status": "planned",
    }
    assert _has_execution_plan(state) is True
    assert _route_after_supervisor(state) == "execute_plan"
    assert _route_after_replan(state) == "execute_plan"
