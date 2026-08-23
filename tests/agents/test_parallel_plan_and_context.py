import json

from app.agents.aggregator import aggregate_agent_outputs
from app.agents.planner import extract_execution_plan


CUSTOMER_MARKET_QUERY = (
    "查询客户 C001 的基本信息和最近消费情况，同时搜索美国市场最近的消费趋势和零售市场趋势，"
    "然后结合客户的消费情况分析该客户是否具有增长潜力"
)


def test_customer_market_plan_keeps_specialist_agents_independent():
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
                                    "task_id": "1",
                                    "agent": "tool-agent",
                                    "query": "查询客户 C001 的基本信息和最近消费情况",
                                    "parallel_group": "A",
                                },
                                {
                                    "task_id": "2",
                                    "agent": "web-agent",
                                    "query": "搜索美国市场最近的消费趋势和零售市场趋势",
                                    "parallel_group": "A",
                                },
                                {
                                    "task_id": "3",
                                    "agent": "knowledge-agent",
                                    "query": "检索知识库中与客户增长潜力和零售市场分析相关的企业知识",
                                    "parallel_group": "A",
                                },
                            ]
                        },
                    }
                ],
            }
        ]
    }

    plan = extract_execution_plan(result)

    assert CUSTOMER_MARKET_QUERY
    assert [task.agent for task in plan.tasks] == [
        "tool-agent",
        "web-agent",
        "knowledge-agent",
    ]
    assert all(task.depends_on == [] for task in plan.tasks)
    assert all(task.parallel_group == "A" for task in plan.tasks)


def test_aggregated_context_does_not_forward_message_history_to_report():
    huge_messages = [
        {"role": "tool", "content": "x" * 12000},
        {"role": "assistant", "content": "最终客户分析证据"},
    ]
    output = {
        "agent_id": "tool-agent",
        "status": "completed",
        "result": {"messages": huge_messages, "debug": {"large": "y" * 10000}},
        "sources": [],
        "errors": [],
        "traces": [{"agent_id": "tool-agent", "elapsed_ms": 22000}],
    }

    context = aggregate_agent_outputs([output])
    serialized = json.dumps(context, ensure_ascii=False)
    report_result = context["successful_results"][0]["result"]

    assert "messages" not in report_result
    assert "traces" not in context["successful_results"][0]
    assert "最终客户分析证据" in report_result["final_evidence"]
    assert len(serialized) < 4000


def test_three_specialist_results_stay_small_for_report_context():
    outputs = []
    for agent_id in ("tool-agent", "web-agent", "knowledge-agent"):
        outputs.append(
            {
                "agent_id": agent_id,
                "status": "completed",
                "result": {
                    "messages": [
                        {"role": "tool", "content": "x" * 12000},
                        {"role": "assistant", "content": f"{agent_id} final evidence"},
                    ],
                    "debug": {"large": "y" * 12000},
                },
                "sources": [],
                "errors": [],
                "traces": [{"agent_id": agent_id, "elapsed_ms": 10000}],
            }
        )

    context = aggregate_agent_outputs(outputs)
    serialized = json.dumps(context, ensure_ascii=False)

    assert len(context["successful_results"]) == 3
    assert all("messages" not in item["result"] for item in context["successful_results"])
    assert all("traces" not in item for item in context["successful_results"])
    assert len(serialized) < 10000
