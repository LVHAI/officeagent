import asyncio

import pytest

from app.core.execution import run_with_timeout


@pytest.mark.asyncio
async def test_run_with_timeout_returns_result():
    async def work():
        return "ok"

    assert await run_with_timeout(work(), timeout=0.1) == "ok"


@pytest.mark.asyncio
async def test_run_with_timeout_raises_on_timeout():
    async def work():
        await asyncio.sleep(0.2)

    with pytest.raises(asyncio.TimeoutError):
        await run_with_timeout(work(), timeout=0.01)
