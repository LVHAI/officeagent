from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.graph import build_workflow

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)


_workflow = None


def _get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


async def run_analysis(query: str) -> dict:
    result = await _get_workflow().ainvoke({"query": query, "errors": []})
    return {
        "query": query,
        "report": result.get("report"),
        "errors": result.get("errors", []),
    }


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    return await run_analysis(request.query)
