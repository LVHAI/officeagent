from app.agents.execution_plan import ExecutionPlan
from app.agents.planner import PLANNER_PROMPT, extract_execution_plan


def _supervisor_result(plan: ExecutionPlan) -> dict:
    return {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": plan.model_dump(mode="json"),
                        "id": "plan-1",
                    }
                ],
            }
        ]
    }


def test_supervisor_plan_preserves_independent_tool_and_web_tasks():
    plan = ExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "task_id": "1",
                    "agent": "tool-agent",
                    "query": "查询客户 C001 的基本信息和最近消费情况",
                },
                {
                    "task_id": "2",
                    "agent": "web-agent",
                    "query": "搜索美国市场最近的消费趋势和零售市场趋势",
                },
            ]
        }
    )

    normalized = extract_execution_plan(_supervisor_result(plan))

    assert [task.agent for task in normalized.tasks] == ["tool-agent", "web-agent"]
    assert all(task.depends_on is None for task in normalized.tasks)


def test_supervisor_plan_keeps_internal_policy_on_knowledge_agent():
    plan = ExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "task_id": "1",
                    "agent": "knowledge-agent",
                    "query": "查询销售管理制度中的A级客户权益",
                }
            ]
        }
    )

    normalized = extract_execution_plan(_supervisor_result(plan))

    assert [task.agent for task in normalized.tasks] == ["knowledge-agent"]


def test_supervisor_prompt_assigns_routing_decision_to_supervisor():
    assert "sole planning and delegation decision center" in PLANNER_PROMPT
    assert "Do not rely on a Python keyword router" in PLANNER_PROMPT
    assert "Knowledge Agent owns the RAG pipeline directly" in PLANNER_PROMPT
    assert "The Tool Agent decides Skill -> MCP internally" in PLANNER_PROMPT
