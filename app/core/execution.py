from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

T = TypeVar("T")


async def run_with_timeout(operation: Awaitable[T], timeout: float) -> T:
    return await asyncio.wait_for(operation, timeout=timeout)
