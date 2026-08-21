from __future__ import annotations

from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


def get_checkpointer():
    """创建进程级 PostgreSQL Checkpointer，保证 API 请求之间共享持久化状态。"""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    _pool = ConnectionPool(settings.postgres_dsn, min_size=1, max_size=8, open=True)
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()
    return _checkpointer
