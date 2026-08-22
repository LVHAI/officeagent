import asyncio

import pytest
from fastapi import HTTPException

from app.api.analysis import run_analysis
from app.core.task_store import InMemoryTaskStore


@pytest.mark.asyncio
async def test_analysis_timeout_returns_504_and_persists_failure(monkeypatch):
    store = InMemoryTaskStore()
    monkeypatch.setattr("app.api.analysis._task_store", store)
    monkeypatch.setattr("app.api.analysis.GLOBAL_TIMEOUT_SECONDS", 0.01)

    class HangingWorkflow:
        async def ainvoke(self, *_args, **_kwargs):
            await asyncio.sleep(1)

    monkeypatch.setattr("app.api.analysis._get_workflow", lambda: HangingWorkflow())

    with pytest.raises(HTTPException) as exc_info:
        await run_analysis("test timeout")

    assert exc_info.value.status_code == 504
    assert "timed out" in str(exc_info.value.detail)
    assert len(store._tasks) == 1
    assert next(iter(store._tasks.values())).status == "failed"
