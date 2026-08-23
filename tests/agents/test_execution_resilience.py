import asyncio

import pytest

from app.core.execution import retry_async


@pytest.mark.asyncio
async def test_retry_async_retries_transient_failures_before_success():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = await retry_async(operation, retries=2, base_delay=0)

    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_async_does_not_retry_cancellation():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await retry_async(operation, retries=3, base_delay=0)

    assert attempts == 1
