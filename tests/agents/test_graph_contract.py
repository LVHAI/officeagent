from app.agents.graph import AgentState, _has_execution_plan, _route_after_supervisor, new_task_state


def test_new_task_state_contains_workflow_identity_and_accumulators():
    state = new_task_state("分析客户流失")
    assert state["query"] == "分析客户流失"
    assert state["task_id"]
    assert state["errors"] == []
    assert state["agent_outputs"] == []
    assert state["replan_count"] == 0


def test_invalid_or_missing_plan_routes_to_report():
    state: AgentState = {"query": "x", "task_id": "t"}
    assert _has_execution_plan(state) is False
    assert _route_after_supervisor(state) == "report"


def test_valid_plan_routes_to_execution():
    state: AgentState = {
        "query": "x",
        "task_id": "t",
        "execution_plan": {
            "tasks": [{"task_id": "k", "agent": "knowledge-agent", "query": "x"}],
            "rationale": "internal knowledge",
        },
    }
    assert _has_execution_plan(state) is True
    assert _route_after_supervisor(state) == "execute_plan"
