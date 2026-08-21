from unittest.mock import patch

import pytest

from app.agents.graph import build_workflow, new_task_state


class FakeAgent:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, payload):
        return self.result


@pytest.mark.asyncio
async def test_workflow_preserves_task_state_and_report():
    with patch("app.agents.graph.create_supervisor", return_value=FakeAgent({"messages": ["knowledge-agent"]})), patch(
        "app.agents.graph.create_report_agent", return_value=FakeAgent({"structured_response": {"summary": "ok"}})
    ):
        workflow = build_workflow()
        state = new_task_state("销售分析")
        result = await workflow.ainvoke(state, config={"configurable": {"thread_id": state["task_id"]}})

    assert result["task_id"] == state["task_id"]
    assert result["report"]
    assert result["traces"]
