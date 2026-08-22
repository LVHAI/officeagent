from __future__ import annotations

import asyncio
import logging
import time
from asyncio import to_thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import GLOBAL_TIMEOUT_SECONDS, build_workflow
from app.core.config import settings
from app.core.execution import run_with_timeout
from app.core.postgres_store import PostgresTaskStore
from app.core.task_store import InMemoryTaskStore, TaskRecord, TaskStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    # 限制输入长度，避免超长 Prompt 放大模型和 Agent 的资源消耗。
    query: str = Field(min_length=1, max_length=8000)


_workflow = None
_task_store: TaskStore = PostgresTaskStore() if settings.environment != "test" else InMemoryTaskStore()


def _get_workflow():
    global _workflow
    if _workflow is None:
        logger.info("analysis.workflow.build.start")
        started = time.perf_counter()
        _workflow = build_workflow()
        logger.info(
            "analysis.workflow.build.completed elapsed_ms=%.1f",
            (time.perf_counter() - started) * 1000,
        )
    return _workflow


def configure_task_store(store: TaskStore) -> None:
    """允许测试和本地调试注入内存实现，避免强依赖 PostgreSQL。"""
    global _task_store
    _task_store = store


def initialize_task_store() -> None:
    """Initialize the configured persistent task store before serving requests."""
    setup = getattr(_task_store, "setup", None)
    if callable(setup):
        started = time.perf_counter()
        logger.info("analysis.task_store.setup.start store=%s", type(_task_store).__name__)
        setup()
        logger.info(
            "analysis.task_store.setup.completed store=%s elapsed_ms=%.1f",
            type(_task_store).__name__,
            (time.perf_counter() - started) * 1000,
        )


async def _save(record: TaskRecord) -> None:
    # psycopg 是同步驱动，放入线程池避免阻塞 Agent 事件循环。
    started = time.perf_counter()
    logger.info("analysis.task_store.save.start task_id=%s status=%s", record.task_id, record.status)
    await to_thread(_task_store.save, record)
    logger.info(
        "analysis.task_store.save.completed task_id=%s status=%s elapsed_ms=%.1f",
        record.task_id,
        record.status,
        (time.perf_counter() - started) * 1000,
    )


async def _get(task_id: str) -> TaskRecord | None:
    return await to_thread(_task_store.get, task_id)


async def run_analysis(query: str) -> dict:
    task_id = str(uuid4())
    request_started = time.perf_counter()
    logger.info("analysis.start task_id=%s query_length=%d", task_id, len(query))
    await _save(TaskRecord(task_id=task_id, status="running"))
    try:
        logger.info(
            "analysis.workflow.prepare task_id=%s timeout_seconds=%.1f",
            task_id,
            GLOBAL_TIMEOUT_SECONDS,
        )
        workflow = _get_workflow()
        logger.info("analysis.workflow.ready task_id=%s", task_id)
        logger.info("analysis.workflow.invoke.start task_id=%s", task_id)
        workflow_started = time.perf_counter()
        result = await run_with_timeout(
            workflow.ainvoke(
                {"query": query, "task_id": task_id, "errors": [], "traces": [], "delegations": []},
                config={"configurable": {"thread_id": task_id}},
            ),
            timeout=GLOBAL_TIMEOUT_SECONDS,
        )
        logger.info(
            "analysis.workflow.invoke.completed task_id=%s elapsed_ms=%.1f errors=%d traces=%d",
            task_id,
            (time.perf_counter() - workflow_started) * 1000,
            len(result.get("errors", [])),
            len(result.get("traces", [])),
        )
        response = {
            "task_id": task_id,
            "query": query,
            "status": result.get("status", "completed" if not result.get("errors") else "partial"),
            "report": result.get("report"),
            "errors": result.get("errors", []),
            "traces": result.get("traces", []),
            "delegations": result.get("delegations", []),
        }
        await _save(
            TaskRecord(
                task_id=task_id,
                status=response["status"],
                result=response,
            )
        )
        logger.info(
            "analysis.completed task_id=%s status=%s total_elapsed_ms=%.1f",
            task_id,
            response["status"],
            (time.perf_counter() - request_started) * 1000,
        )
        return response
    except asyncio.TimeoutError:
        logger.error(
            "analysis.timeout task_id=%s timeout_seconds=%.1f total_elapsed_ms=%.1f",
            task_id,
            GLOBAL_TIMEOUT_SECONDS,
            (time.perf_counter() - request_started) * 1000,
        )
        await _save(
            TaskRecord(
                task_id=task_id,
                status="failed",
                error=f"analysis timeout after {GLOBAL_TIMEOUT_SECONDS:.1f}s",
            )
        )
        raise HTTPException(
            status_code=504,
            detail=f"analysis timed out after {GLOBAL_TIMEOUT_SECONDS:.1f}s; task_id={task_id}",
        )
    except Exception as exc:
        logger.exception(
            "analysis.failed task_id=%s total_elapsed_ms=%.1f error=%s",
            task_id,
            (time.perf_counter() - request_started) * 1000,
            exc,
        )
        await _save(TaskRecord(task_id=task_id, status="failed", error=str(exc)))
        raise


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    return await run_analysis(request.query)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    record = await _get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "task_id": record.task_id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "updated_at": record.updated_at.isoformat(),
    }
