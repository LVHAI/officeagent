from app.agents.planner import extract_execution_plan


def test_extract_execution_plan_normalizes_general_purpose_agent():
    result = {
        "messages": [
            {
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {
                                    "task_id": "t1",
                                    "agent": "general-purpose",
                                    "query": "查询客户 C001",
                                    "parallel_group": None,
                                    "depends_on": None,
                                    "constraints": None,
                                }
                            ],
                            "rationale": None,
                        },
                    }
                ]
            }
        ]
    }

    plan = extract_execution_plan(result)

    assert plan.tasks[0].agent == "tool-agent"
    assert plan.tasks[0].parallel_group == "default"
    assert plan.tasks[0].depends_on == []
    assert plan.tasks[0].constraints == {}
    assert plan.rationale == ""


def test_extract_execution_plan_rejects_unknown_agent():
    result = {
        "messages": [
            {
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {
                                    "task_id": "t1",
                                    "agent": "unknown-agent",
                                    "query": "test",
                                }
                            ]
                        },
                    }
                ]
            }
        ]
    }

    try:
        extract_execution_plan(result)
    except Exception as exc:
        assert "agent" in str(exc)
    else:
        raise AssertionError("unknown planner agent must be rejected")
