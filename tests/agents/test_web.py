from app.agents.web import normalize_tavily_results


def test_web_results_keep_only_url_backed_evidence():
    results = normalize_tavily_results(
        {
            "results": [
                {"url": "https://example.com/a", "title": "A", "source": "tavily"},
                {"title": "missing url"},
            ]
        }
    )
    assert len(results) == 1
    assert results[0].url == "https://example.com/a"
    assert results[0].retrieved_at
