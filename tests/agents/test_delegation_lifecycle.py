from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.graph import new_task_state, supervisor_node


@pytest.mark.asyncio
async def test_delegation_without_tool_result_remains_delegated_not_completed():
    agent = Mock()
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {
                    "type": "ai",
                    "tool_calls": [
                        {
                            "name": "task",
                            "args": {"subagent_type": "web-agent", "description": "搜索最新市场数据"},
                            "id": "call-web",
                        }
                    ],
                }
            ]
        }
    )

    with patch("app.agents.graph.create_supervisor", return_value=agent):
        result = await supervisor_node(new_task_state("搜索最新市场数据"))

    assert result["delegations"][0]["status"] == "delegated"
    assert result["delegations"][0]["child_agent_id"] == "web-agent"
    assert result["agent_outputs"][0]["agent_id"] == "supervisor"


@pytest.mark.asyncio
async def test_failed_delegation_is_preserved_for_partial_reporting():
    agent = Mock()
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {
                    "type": "ai",
                    "tool_calls": [
                        {
                            "name": "task",
                            "args": {"subagent_type": "tool-agent", "description": "查询 CRM"},
                            "id": "call-tool",
                        }
                    ],
                },
                {
                    "type": "tool",
                    "tool_call_id": "call-tool",
                    "content": "error: database unavailable",
                },
            ]
        }
    )

    with patch("app.agents.graph.create_supervisor", return_value=agent):
        result = await supervisor_node(new_task_state("查询 CRM"))

    assert result["delegations"][0]["status"] == "failed"
    assert result["delegations"][0]["error"]
    assert result["agent_outputs"][0]["status"] == "completed"
