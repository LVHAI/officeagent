import asyncio

import pytest

from app.core.execution import gather_bounded, run_with_timeout


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


@pytest.mark.asyncio
async def test_gather_bounded_limits_concurrency():
    active = 0
    peak = 0

    async def job() -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return 1

    result = await gather_bounded([job() for _ in range(6)], limit=2)

    assert result == [1] * 6
    assert peak <= 2
