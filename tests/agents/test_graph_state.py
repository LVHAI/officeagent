from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.graph import build_workflow, new_task_state
from app.core.config import settings


class FakeAgent:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, payload):
        return self.result


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
                                {"task_id": "knowledge", "agent": "knowledge-agent", "query": "查销售制度"}
                            ]
                        },
                        "id": "plan-1",
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_workflow_preserves_task_state_and_report(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    with patch("app.agents.graph.create_execution_planner", return_value=FakeAgent(_plan_result())), patch(
        "app.agents.graph.create_knowledge_agent",
        return_value=FakeAgent({"messages": [{"type": "ai", "content": "制度结果"}]}),
    ), patch(
        "app.agents.graph.create_report_agent",
        return_value=FakeAgent({"summary": "ok"}),
    ):
        workflow = build_workflow()
        state = new_task_state("销售分析")
        result = await workflow.ainvoke(state, config={"configurable": {"thread_id": state["task_id"]}})

    assert result["task_id"] == state["task_id"]
    assert result["report"]
    assert result["traces"]
    assert result["agent_outputs"]
