from app.agents.execution_plan import ExecutionPlan
from app.agents.planner import validate_agent_selection


QUERY = (
    "查询客户 C001 的基本信息和最近消费情况，同时搜索美国市场最近的消费趋势和零售市场趋势，"
    "然后结合客户的消费情况分析该客户是否具有增长潜力"
)


def test_customer_and_current_market_query_does_not_select_knowledge_agent():
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
                {
                    "task_id": "3",
                    "agent": "knowledge-agent",
                    "query": "分析客户增长潜力相关知识",
                },
            ]
        }
    )

    normalized = validate_agent_selection(QUERY, plan)

    assert [task.agent for task in normalized.tasks] == ["tool-agent", "web-agent"]


def test_internal_policy_query_keeps_knowledge_agent():
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

    normalized = validate_agent_selection("查询销售管理制度中的A级客户权益", plan)

    assert [task.agent for task in normalized.tasks] == ["knowledge-agent"]
