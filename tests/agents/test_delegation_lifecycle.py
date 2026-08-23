from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.graph import aggregate_node, replan_node


def _plan_result():
    return {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "retry-web", "agent": "web-agent", "query": "重新搜索最新市场数据"}
                            ]
                        },
                        "id": "plan-2",
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_failed_agent_output_triggers_one_replan():
    state = {
        "task_id": "task-1",
        "query": "查询最新市场数据",
        "replan_count": 0,
        "agent_outputs": [
            {"agent_id": "web-agent", "status": "failed", "result": None, "errors": ["timeout"]}
        ],
        "errors": ["web-agent: timeout"],
        "traces": [],
        "delegations": [],
    }
    aggregated = await aggregate_node(state)
    state.update(aggregated)

    planner = Mock()
    planner.ainvoke = AsyncMock(return_value=_plan_result())
    with patch("app.agents.graph.create_execution_planner", return_value=planner):
        result = await replan_node(state)

    assert result["replan_count"] == 1
    assert result["execution_plan"]["tasks"][0]["agent"] == "web-agent"
