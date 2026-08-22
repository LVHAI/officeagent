from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.agents.deepagents import _ReportAgent


def _agent() -> _ReportAgent:
    return object.__new__(_ReportAgent)


def test_extract_report_from_tool_call() -> None:
    response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "submit_analysis_report",
                "args": {
                    "summary": "Summary",
                    "findings": [
                        {"title": "Finding", "evidence": "Evidence", "confidence": 0.9}
                    ],
                    "recommendations": ["Recommendation"],
                    "sources": [{"kind": "document", "title": "Doc", "uri": "doc://1"}],
                    "partial_results": [],
                },
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )

    report = _agent()._extract_report(response)

    assert report.summary == "Summary"
    assert report.recommendations == ["Recommendation"]
    assert report.findings[0].confidence == 0.9


def test_extract_report_rejects_missing_tool_call() -> None:
    response = SimpleNamespace(tool_calls=[])

    with pytest.raises(ValueError, match="did not call submit_analysis_report"):
        _agent()._extract_report(response)


def test_extract_report_rejects_invalid_recommendation_shape() -> None:
    response = SimpleNamespace(
        tool_calls=[
            {
                "name": "submit_analysis_report",
                "args": {
                    "summary": "Summary",
                    "findings": [],
                    "recommendations": [{"description": "not a string"}],
                    "sources": [],
                    "partial_results": [],
                },
            }
        ]
    )

    with pytest.raises(Exception):
        _agent()._extract_report(response)


def test_extract_report_rejects_multiple_tool_calls() -> None:
    response = SimpleNamespace(
        tool_calls=[
            {"name": "submit_analysis_report", "args": {}},
            {"name": "submit_analysis_report", "args": {}},
        ]
    )

    with pytest.raises(ValueError, match="exactly once"):
        _agent()._extract_report(response)
