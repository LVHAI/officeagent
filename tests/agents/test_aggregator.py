from app.agents.aggregator import aggregate_agent_outputs, compact_result_for_report


def test_aggregation_preserves_sources_and_separates_failures():
    context = aggregate_agent_outputs(
        [
            {
                "agent_id": "knowledge-agent",
                "status": "completed",
                "result": {"answer": "policy"},
                "sources": [
                    {"kind": "knowledge", "title": "policy.pdf", "uri": "", "metadata": {"page": 3}}
                ],
                "errors": [],
            },
            {
                "agent_id": "web-agent",
                "status": "failed",
                "result": None,
                "sources": [],
                "errors": ["timeout"],
            },
        ]
    )
    assert len(context["successful_results"]) == 1
    assert len(context["failed_results"]) == 1
    assert context["sources"][0]["metadata"]["page"] == 3
    assert context["has_partial_result"] is True


def test_report_context_is_bounded():
    value = compact_result_for_report("x" * 100, limit=20)
    assert len(value) < 100
    assert value.endswith("...[truncated]")
