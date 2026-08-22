import asyncio
import logging

import pytest

from app.agents.graph import _invoke


class SlowAgent:
    async def ainvoke(self, _payload):
        await asyncio.sleep(0.03)
        return {"ok": True}


@pytest.mark.asyncio
async def test_agent_emits_progress_log_while_long_call_is_running(monkeypatch, caplog):
    monkeypatch.setattr("app.agents.graph.AGENT_PROGRESS_LOG_INTERVAL_SECONDS", 0.01)
    with caplog.at_level(logging.INFO, logger="app.agents.graph"):
        result, trace = await _invoke(SlowAgent(), "hello", "supervisor", "task-log")

    assert result == {"ok": True}
    assert trace["status"] == "completed"
    assert "agent.invoke.start task_id=task-log agent=supervisor" in caplog.text
    assert "agent.invoke.progress task_id=task-log agent=supervisor" in caplog.text
    assert "agent.invoke.completed task_id=task-log agent=supervisor" in caplog.text
