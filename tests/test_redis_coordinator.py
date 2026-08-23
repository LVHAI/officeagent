from unittest.mock import AsyncMock

import pytest

from app.core.redis_state import RedisTaskCoordinator


@pytest.mark.asyncio
async def test_redis_task_coordinator_tracks_status_with_ttl():
    client = AsyncMock()
    coordinator = RedisTaskCoordinator(client)

    await coordinator.set_status("t1", "running")
    await coordinator.set_status("t1", "completed")

    assert client.set.await_count == 2
    assert client.set.await_args_list[-1].args[0] == "officeagent:task:t1"
    assert client.set.await_args_list[-1].args[1] == "completed"
