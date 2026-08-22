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
