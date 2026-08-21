from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import build_workflow
from app.core.config import settings
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
        # Workflow 只构建一次，Checkpoint 生命周期与本地开发进程一致。
        _workflow = build_workflow()
    return _workflow


def configure_task_store(store: TaskStore) -> None:
    """允许测试和本地调试注入内存实现，避免强依赖 PostgreSQL。"""
    global _task_store
    _task_store = store


async def run_analysis(query: str) -> dict:
    task_id = str(uuid4())
    _task_store.save(TaskRecord(task_id=task_id, status="running"))
    try:
        # task_id 同时作为 LangGraph checkpoint 的 thread_id，贯穿整个执行链路。
        result = await _get_workflow().ainvoke(
            {"query": query, "task_id": task_id, "errors": [], "traces": []},
            config={"configurable": {"thread_id": task_id}},
        )
        response = {
            "task_id": task_id,
            "query": query,
            "report": result.get("report"),
            "errors": result.get("errors", []),
            # Trace 用于企业审计，也方便本地调试 Agent 执行链路。
            "traces": result.get("traces", []),
        }
        status = "failed" if response["errors"] else "completed"
        _task_store.save(TaskRecord(task_id=task_id, status=status, result=response))
        return response
    except Exception as exc:
        # 失败状态先落库，调用方可以通过任务查询接口定位失败原因。
        _task_store.save(TaskRecord(task_id=task_id, status="failed", error=str(exc)))
        raise


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    # API 层保持轻量，只负责参数校验和调用 Agent Workflow。
    return await run_analysis(request.query)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """查询任务状态；本地开发默认使用 PostgreSQL，测试可注入内存实现。"""
    record = _task_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "task_id": record.task_id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "updated_at": record.updated_at.isoformat(),
    }
