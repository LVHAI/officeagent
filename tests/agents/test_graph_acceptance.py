from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.graph import build_workflow, new_task_state, supervisor_node
from app.core.config import settings


def _plan_result(agent="tool-agent", query="查询 CRM"):
    return {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {
                        "name": "submit_execution_plan",
                        "args": {
                            "tasks": [
                                {"task_id": "task-1", "agent": agent, "query": query}
                            ],
                            "rationale": "minimum required agent",
                        },
                        "id": "plan-1",
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_supervisor_failure_isolated_as_partial_result():
    failed = Mock()
    failed.ainvoke = AsyncMock(side_effect=RuntimeError("model unavailable"))

    with patch("app.agents.graph.create_execution_planner", return_value=failed):
        result = await supervisor_node(new_task_state("分析销售趋势"))

    assert result["status"] == "partial"
    assert result["errors"]
    assert result["traces"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_supervisor_only_creates_planned_delegation():
    planner = Mock()
    planner.ainvoke = AsyncMock(return_value=_plan_result())

    with patch("app.agents.graph.create_execution_planner", return_value=planner):
        result = await supervisor_node(new_task_state("查询 CRM"))

    assert len(result["delegations"]) == 1
    delegation = result["delegations"][0]
    assert delegation["child_agent_id"] == "tool-agent"
    assert delegation["status"] == "planned"


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
    assert first["agent_outputs"] == []
    assert first["replan_count"] == 0
    assert second["errors"] == []
