import asyncio
from unittest.mock import patch

import pytest

from app.agents.graph import execute_plan_node


class FakeAgent:
    def __init__(self, agent_id, active):
        self.agent_id = agent_id
        self.active = active

    async def ainvoke(self, payload):
        self.active[0] += 1
        self.active[1] = max(self.active[1], self.active[0])
        await asyncio.sleep(0.03)
        self.active[0] -= 1
        return {"messages": [{"type": "ai", "content": f"{self.agent_id} ok"}]}


@pytest.mark.asyncio
async def test_independent_agents_execute_concurrently():
    active = [0, 0]
    state = {
        "task_id": "task-1",
        "execution_plan": {
            "tasks": [
                {"task_id": "k", "agent": "knowledge-agent", "query": "知识"},
                {"task_id": "t", "agent": "tool-agent", "query": "客户"},
                {"task_id": "w", "agent": "web-agent", "query": "最新"},
            ]
        },
        "agent_outputs": [],
        "errors": [],
        "traces": [],
        "delegations": [],
    }

    with patch("app.agents.graph.create_knowledge_agent", return_value=FakeAgent("k", active)), patch(
        "app.agents.graph.create_tool_agent", return_value=FakeAgent("t", active)
    ), patch("app.agents.graph.create_web_agent", return_value=FakeAgent("w", active)):
        result = await execute_plan_node(state)

    assert len(result["agent_outputs"]) == 3
    assert all(item["status"] == "completed" for item in result["agent_outputs"])
    assert active[1] >= 2
