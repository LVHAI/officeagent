from __future__ import annotations

from pydantic import BaseModel, Field


class ReportFinding(BaseModel):
    title: str
    evidence: str
    confidence: float = Field(ge=0, le=1)


class ReportSource(BaseModel):
    kind: str
    title: str = ""
    uri: str = ""


class AnalysisReport(BaseModel):
    summary: str
    findings: list[ReportFinding] = []
    recommendations: list[str] = []
    sources: list[ReportSource] = []
    partial_results: list[str] = []
