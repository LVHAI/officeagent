import json

from app.agents.planner import extract_execution_plan, submit_execution_plan


def test_submit_execution_plan_returns_canonical_plan():
    value = json.loads(
        submit_execution_plan(
            [{"task_id": "k1", "agent": "knowledge-agent", "query": "查询制度"}],
            "internal evidence",
        )
    )
    assert value["tasks"][0]["agent"] == "knowledge-agent"
    assert value["rationale"] == "internal evidence"


def test_extract_execution_plan_accepts_one_structured_tool_call():
    result = {
        "messages": [
            {
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "w1", "agent": "web", "query": "latest trend"}
                            ]
                        },
                    }
                ]
            }
        ]
    }
    plan = extract_execution_plan(result)
    assert plan.tasks[0].agent == "web-agent"


def test_extract_execution_plan_rejects_missing_submission():
    try:
        extract_execution_plan({"messages": []})
    except ValueError as exc:
        assert "exactly once" in str(exc)
    else:
        raise AssertionError("missing execution plan must fail")
