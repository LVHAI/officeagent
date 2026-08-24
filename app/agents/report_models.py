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
    findings: list[ReportFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sources: list[ReportSource] = Field(default_factory=list)
    partial_results: list[str] = Field(default_factory=list)
