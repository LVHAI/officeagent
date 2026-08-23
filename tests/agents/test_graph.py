from app.agents.graph import _task_query


def test_task_query_includes_dependency_results_only_for_dependent_task():
    query = _task_query(
        "use upstream evidence",
        {"db": {"status": "completed", "result": {"rows": [1, 2]}, "errors": []}},
    )

    assert "use upstream evidence" in query
    assert "rows" in query
    assert "[Dependency Results]" in query
