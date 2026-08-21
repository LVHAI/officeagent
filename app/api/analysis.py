from __future__ import annotations

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
        # Workflow 只构建一次，避免每个 HTTP 请求重复创建 LangGraph 图。
        _workflow = build_workflow()
    return _workflow


async def run_analysis(query: str) -> dict:
    # 每个请求使用独立 State；Graph 内部负责 Agent 并发和状态合并。
    result = await _get_workflow().ainvoke({"query": query, "errors": []})
    return {
        "query": query,
        "report": result.get("report"),
        "errors": result.get("errors", []),
    }


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    # API 层保持轻量，只负责参数校验和调用 Agent Workflow。
    return await run_analysis(request.query)
