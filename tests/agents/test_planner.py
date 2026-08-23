from app.agents.planner import extract_execution_plan


def test_extract_execution_plan_from_structured_tool_call():
    result = {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "k", "agent": "knowledge-agent", "query": "查制度"}
                            ]
                        },
                        "id": "plan-1",
                    }
                ],
            }
        ]
    }
    plan = extract_execution_plan(result)
    assert plan.tasks[0].agent == "knowledge-agent"


def test_extract_execution_plan_deduplicates_identical_tool_calls():
    call = {
        "name": "submit_execution_plan",
        "args": {
            "tasks": [
                {"task_id": "k", "agent": "knowledge-agent", "query": "查制度"}
            ]
        },
    }
    result = {"messages": [{"tool_calls": [call, {**call, "id": "duplicate"}]}]}

    plan = extract_execution_plan(result)

    assert len(plan.tasks) == 1
    assert plan.tasks[0].agent == "knowledge-agent"


def test_extract_execution_plan_rejects_different_tool_calls():
    result = {
        "messages": [
            {
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "k", "agent": "knowledge-agent", "query": "查制度"}
                            ]
                        },
                    },
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "w", "agent": "web-agent", "query": "查新闻"}
                            ]
                        },
                    },
                ]
            }
        ]
    }

    try:
        extract_execution_plan(result)
    except ValueError as exc:
        assert "multiple different execution plans" in str(exc)
    else:
        raise AssertionError("expected ValueError")
