import pytest
from pydantic import ValidationError

from app.api.analysis import AnalyzeRequest, _compact_agent_output


def test_analyze_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        AnalyzeRequest(query="")


def test_analyze_request_rejects_oversized_query():
    with pytest.raises(ValidationError):
        AnalyzeRequest(query="x" * 8001)


def test_analyze_request_accepts_normal_query():
    request = AnalyzeRequest(query="分析华东客户流失原因")
    assert request.query == "分析华东客户流失原因"


def test_compact_agent_output_drops_raw_message_history():
    output = {
        "agent_id": "tool-agent",
        "status": "completed",
        "result": {
            "messages": [
                {"role": "tool", "content": "large intermediate SQL result"},
                {"role": "assistant", "content": "final evidence"},
            ]
        },
        "sources": [],
        "errors": [],
        "elapsed_ms": 123.4,
    }

    compact = _compact_agent_output(output)

    assert compact["result"] == {"final_evidence": "final evidence"}
    assert "messages" not in compact["result"]
    assert compact["elapsed_ms"] == 123.4
