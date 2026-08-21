import pytest

from app.core.retry import retry_async


@pytest.mark.asyncio
async def test_retry_async_recovers_after_transient_failure():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    assert await retry_async(operation, retries=3, base_delay=0) == "ok"
    assert attempts == 3
