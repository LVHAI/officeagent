import json

from app.agents.planner import PLAN_TOOL, create_execution_planner, extract_execution_plan


def test_create_execution_planner_is_importable():
    planner = create_execution_planner()
    assert planner is not None


def test_planner_tool_exposes_explicit_function_schema():
    schema = PLAN_TOOL.args_schema.model_json_schema()
    task = schema["$defs"]["ExecutionTaskInput"]
    assert "parallel_group" in task["properties"]
    assert "null" in str(task["properties"]["parallel_group"])


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


def test_extract_execution_plan_accepts_model_nullable_defaults():
    result = {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {
                                    "task_id": "k",
                                    "agent": "knowledge-agent",
                                    "query": "查制度",
                                    "depends_on": None,
                                    "parallel_group": None,
                                    "constraints": None,
                                }
                            ],
                            "rationale": None,
                        },
                    }
                ],
            }
        ]
    }

    plan = extract_execution_plan(result)

    assert plan.tasks[0].parallel_group == "default"
    assert plan.tasks[0].depends_on == []
    assert plan.tasks[0].constraints == {}
    assert plan.rationale == ""


def test_extract_execution_plan_from_executed_tool_message():
    payload = {
        "tasks": [
            {"task_id": "w", "agent": "web-agent", "query": "查最新市场信息"}
        ],
        "rationale": "需要当前外部信息",
    }
    result = {
        "messages": [
            {
                "type": "tool",
                "name": "submit_execution_plan",
                "content": json.dumps(payload),
                "tool_call_id": "call-1",
            }
        ]
    }

    plan = extract_execution_plan(result)

    assert plan.tasks[0].agent == "web-agent"
    assert plan.rationale == "需要当前外部信息"


def test_extract_execution_plan_deduplicates_ai_and_tool_message_with_defaults():
    args = {
        "tasks": [
            {"task_id": "k", "agent": "knowledge-agent", "query": "查制度"}
        ]
    }
    executed = {
        "tasks": [
            {
                "task_id": "k",
                "agent": "knowledge-agent",
                "query": "查制度",
                "depends_on": [],
                "parallel_group": "default",
                "constraints": {},
            }
        ],
        "rationale": "",
    }
    result = {
        "messages": [
            {"type": "ai", "tool_calls": [{"name": "submit_execution_plan", "args": args}]},
            {
                "type": "tool",
                "name": "submit_execution_plan",
                "content": json.dumps(executed),
                "tool_call_id": "call-1",
            },
        ]
    }

    plan = extract_execution_plan(result)

    assert len(plan.tasks) == 1
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
