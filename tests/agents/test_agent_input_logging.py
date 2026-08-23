from app.agents.graph import _agent_input_log


def test_agent_input_log_contains_actual_input_and_context():
    payload = _agent_input_log(
        task_id="task-1",
        agent_id="report",
        parent_agent_id="supervisor",
        query='{"query":"推荐几道菜","evidence":{"final_evidence":"红烧鱼"}}',
    )

    assert payload["task_id"] == "task-1"
    assert payload["agent"] == "report"
    assert payload["parent"] == "supervisor"
    assert payload["input_length"] == len(payload["input"])
    assert payload["input"] == '{"query":"推荐几道菜","evidence":{"final_evidence":"红烧鱼"}}'
