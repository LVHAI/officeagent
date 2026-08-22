from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


def get_checkpointer():
    """创建进程级 PostgreSQL Checkpointer，并使用正确的连接参数初始化迁移。"""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    # LangGraph PostgreSQL 初始化包含 CREATE INDEX CONCURRENTLY，必须在事务外执行。
    # dict_row 也是 PostgresSaver 读取 checkpoint 行时的必要配置。
    _pool = ConnectionPool(
        settings.postgres_dsn,
        min_size=1,
        max_size=8,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=True,
    )
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()
    return _checkpointer
