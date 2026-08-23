from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.graph import build_workflow, new_task_state, supervisor_node
from app.core.config import settings


@pytest.mark.asyncio
async def test_supervisor_failure_isolated_as_partial_result():
    failed = Mock()
    failed.ainvoke = AsyncMock(side_effect=RuntimeError("model unavailable"))

    with patch("app.agents.graph.create_supervisor", return_value=failed):
        result = await supervisor_node(new_task_state("分析销售趋势"))

    assert result["status"] == "partial"
    assert result["errors"]
    assert result["traces"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_delegation_trace_comes_from_real_task_tool_call():
    agent = Mock()
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {
                    "type": "ai",
                    "tool_calls": [
                        {
                            "name": "task",
                            "args": {
                                "subagent_type": "tool-agent",
                                "description": "查询 CRM 客户数据",
                            },
                            "id": "call-1",
                        }
                    ],
                },
                {
                    "type": "tool",
                    "tool_call_id": "call-1",
                    "content": "tool-agent result",
                },
            ]
        }
    )

    with patch("app.agents.graph.create_supervisor", return_value=agent):
        result = await supervisor_node(new_task_state("分析客户流失"))

    assert len(result["delegations"]) == 1
    delegation = result["delegations"][0]
    assert delegation["child_agent_id"] == "tool-agent"
    assert delegation["status"] == "delegated"
    assert delegation["reason"] == "查询 CRM 客户数据"


@pytest.mark.asyncio
async def test_supervisor_text_mention_does_not_create_fake_delegation():
    agent = Mock()
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {"type": "ai", "content": "建议后续考虑 tool-agent 和 web-agent。"},
            ]
        }
    )

    with patch("app.agents.graph.create_supervisor", return_value=agent):
        result = await supervisor_node(new_task_state("给出分析建议"))

    assert result["delegations"] == []


def test_workflow_uses_memory_checkpoint_for_tests(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    workflow = build_workflow()
    assert workflow is not None


def test_new_task_state_has_isolated_execution_state():
    first = new_task_state("query-1")
    second = new_task_state("query-2")

    assert first["task_id"] != second["task_id"]
    assert first["errors"] == []
    assert first["traces"] == []
    assert first["delegations"] == []
    assert second["errors"] == []
