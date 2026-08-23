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
