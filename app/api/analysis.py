from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.graph import build_workflow
from app.core.execution import run_with_timeout

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    # 限制输入长度，避免超长 Prompt 直接放大模型和 Agent 的资源消耗。
    query: str = Field(min_length=1, max_length=8000)


_workflow = None
# 整个分析请求的全局超时；单个 Agent 仍由 Graph 层使用更短的局部超时保护。
WORKFLOW_TIMEOUT_SECONDS = 120.0


def _get_workflow():
    global _workflow
    if _workflow is None:
        # Workflow 只构建一次，避免每个 HTTP 请求重复创建 LangGraph 图。
        _workflow = build_workflow()
    return _workflow


async def run_analysis(query: str) -> dict:
    # 每个 HTTP 请求生成独立 task_id，贯穿 Supervisor、Worker 和 Report Trace。
    task_id = str(uuid4())
    try:
        # 全局超时负责兜底，防止局部 Agent 都正常但整个工作流仍长期占用请求资源。
        result = await run_with_timeout(
            _get_workflow().ainvoke(
                {"query": query, "task_id": task_id, "errors": [], "traces": []}
            ),
            timeout=WORKFLOW_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        # 超时不伪造 Report；调用方可以根据 task_id 查询审计记录并继续排查。
        return {
            "task_id": task_id,
            "query": query,
            "report": None,
            "errors": ["workflow timeout"],
            "traces": [],
        }

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
