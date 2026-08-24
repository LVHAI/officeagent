from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings


_async_pool: AsyncConnectionPool | None = None
_async_checkpointer: AsyncPostgresSaver | None = None


async def initialize_checkpointer() -> AsyncPostgresSaver:
    """Initialize the async PostgreSQL checkpointer used by LangGraph.\n\n    LangGraph's async execution path calls ``aget_tuple``/other async methods, so\n    production must use ``AsyncPostgresSaver`` rather than the synchronous saver.\n    The pool is configured with autocommit because the checkpoint migrations use\n    ``CREATE INDEX CONCURRENTLY``.\n    """
    global _async_pool, _async_checkpointer
    if _async_checkpointer is not None:
        return _async_checkpointer

    _async_pool = AsyncConnectionPool(
        settings.postgres_dsn,
        min_size=1,
        max_size=8,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False,
    )
    await _async_pool.open()
    _async_checkpointer = AsyncPostgresSaver(_async_pool)
    await _async_checkpointer.setup()
    return _async_checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    """Return the initialized async checkpointer for workflow compilation."""
    if _async_checkpointer is None:
        raise RuntimeError(
            "PostgreSQL checkpointer is not initialized; call initialize_checkpointer() during startup"
        )
    return _async_checkpointer


async def close_checkpointer() -> None:
    """Close the process-level async PostgreSQL pool during application shutdown."""
    global _async_pool, _async_checkpointer
    if _async_pool is not None:
        await _async_pool.close()
    _async_pool = None
    _async_checkpointer = None
