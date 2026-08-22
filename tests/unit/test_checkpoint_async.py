from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.checkpoint as checkpoint
from app.agents.graph import build_workflow
from app.core.config import settings


@pytest.mark.asyncio
async def test_initialize_checkpointer_uses_async_postgres_saver(monkeypatch):
    class FakePool:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.opened = False

        async def open(self):
            self.opened = True

        async def close(self):
            self.opened = False

    class FakeSaver:
        def __init__(self, pool):
            self.pool = pool
            self.setup = AsyncMock()
            self.aget_tuple = AsyncMock(return_value=None)

    fake_pool = FakePool
    fake_saver = FakeSaver
    monkeypatch.setattr(checkpoint, "AsyncConnectionPool", fake_pool)
    monkeypatch.setattr(checkpoint, "AsyncPostgresSaver", fake_saver)
    monkeypatch.setattr(checkpoint, "_async_pool", None)
    monkeypatch.setattr(checkpoint, "_async_checkpointer", None)

    saver = await checkpoint.initialize_checkpointer()

    assert isinstance(saver, FakeSaver)
    assert saver.pool.opened is True
    saver.setup.assert_awaited_once()
    assert callable(saver.aget_tuple)


@pytest.mark.asyncio
async def test_close_checkpointer_closes_async_pool(monkeypatch):
    pool = MagicMock()
    pool.close = AsyncMock()
    monkeypatch.setattr(checkpoint, "_async_pool", pool)
    monkeypatch.setattr(checkpoint, "_async_checkpointer", MagicMock())

    await checkpoint.close_checkpointer()

    pool.close.assert_awaited_once()
    assert checkpoint._async_pool is None
    assert checkpoint._async_checkpointer is None


def test_production_workflow_uses_initialized_async_checkpointer(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    async_saver = MagicMock()
    monkeypatch.setattr(checkpoint, "_async_checkpointer", async_saver)

    workflow = build_workflow()

    assert workflow.checkpointer is async_saver
