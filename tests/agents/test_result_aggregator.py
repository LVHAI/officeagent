from app.agents.aggregator import aggregate_agent_outputs


def test_aggregator_preserves_partial_results_and_deduplicates_sources():
    result = {
        "messages": [
            {
                "type": "tool",
                "content": '{"sources":[{"document":"sales.md","page":3,"section":"客户"}]}'
            }
        ]
    }
    outputs = [
        {"agent_id": "knowledge-agent", "status": "completed", "result": result, "sources": []},
        {"agent_id": "web-agent", "status": "failed", "result": None, "errors": ["timeout"]},
    ]

    context = aggregate_agent_outputs(outputs)

    assert len(context["successful_results"]) == 1
    assert len(context["failed_results"]) == 1
    assert context["has_partial_result"] is True
    assert len(context["sources"]) == 1
    assert context["sources"][0]["kind"] == "knowledge"
