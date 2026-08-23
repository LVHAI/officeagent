import pytest
from pydantic import ValidationError

from app.api.analysis import AnalyzeRequest


def test_analyze_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        AnalyzeRequest(query="")


def test_analyze_request_rejects_oversized_query():
    with pytest.raises(ValidationError):
        AnalyzeRequest(query="x" * 8001)


def test_analyze_request_accepts_normal_query():
    request = AnalyzeRequest(query="分析华东客户流失原因")
    assert request.query == "分析华东客户流失原因"
