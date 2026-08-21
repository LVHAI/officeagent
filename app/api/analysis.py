from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.graph import build_workflow

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    # 限制输入长度，避免超长 Prompt 直接放大模型和 Agent 的资源消耗。
    query: str = Field(min_length=1, max_length=8000)


_workflow = None


def _get_workflow():
    global _workflow
    if _workflow is None:
        # Workflow 只构建一次，Checkpoint 生命周期与本地开发进程一致。
        _workflow = build_workflow()
    return _workflow


async def run_analysis(query: str) -> dict:
    task_id = str(uuid4())
    # task_id 同时作为 LangGraph checkpoint 的 thread_id，支持按任务恢复和检查状态。
    result = await _get_workflow().ainvoke(
        {"query": query, "task_id": task_id, "errors": [], "traces": []},
        config={"configurable": {"thread_id": task_id}},
    )
    return {
        "task_id": task_id,
        "query": query,
        "report": result.get("report"),
        "errors": result.get("errors", []),
        # Trace 用于企业审计，也方便本地调试 Agent 执行链路。
        "traces": result.get("traces", []),
    }


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    # API 层保持轻量，只负责参数校验和调用 Agent Workflow。
    return await run_analysis(request.query)
