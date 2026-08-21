from asyncio import to_thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import GLOBAL_TIMEOUT_SECONDS, build_workflow
from app.core.config import settings
from app.core.execution import run_with_timeout
from app.core.postgres_store import PostgresTaskStore
from app.core.task_store import InMemoryTaskStore, TaskRecord, TaskStore

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    # 限制输入长度，避免超长 Prompt 放大模型和 Agent 的资源消耗。
    query: str = Field(min_length=1, max_length=8000)


_workflow = None
_task_store: TaskStore = PostgresTaskStore() if settings.environment != "test" else InMemoryTaskStore()


def _get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


def configure_task_store(store: TaskStore) -> None:
    """允许测试和本地调试注入内存实现，避免强依赖 PostgreSQL。"""
    global _task_store
    _task_store = store


async def _save(record: TaskRecord) -> None:
    # psycopg 是同步驱动，放入线程池避免阻塞 Agent 事件循环。
    await to_thread(_task_store.save, record)


async def _get(task_id: str) -> TaskRecord | None:
    return await to_thread(_task_store.get, task_id)


async def run_analysis(query: str) -> dict:
    task_id = str(uuid4())
    await _save(TaskRecord(task_id=task_id, status="running"))
    try:
        result = await run_with_timeout(
            _get_workflow().ainvoke(
                {"query": query, "task_id": task_id, "errors": [], "traces": [], "delegations": []},
                config={"configurable": {"thread_id": task_id}},
            ),
            timeout=GLOBAL_TIMEOUT_SECONDS,
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
        return response
    except Exception as exc:
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
