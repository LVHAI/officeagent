from __future__ import annotations

import pytest

from app.agents.deepagents import build_tavily_search
from app.core.config import settings


@pytest.mark.asyncio
async def test_web_search_fails_closed_without_tavily_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", None)

    search = build_tavily_search()

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        await search.ainvoke({"query": "latest US retail trend"})


@pytest.mark.asyncio
async def test_web_search_emits_result_count(monkeypatch, caplog):
    class FakeTavily:
        async def ainvoke(self, payload):
            assert payload == {"query": "latest US retail trend"}
            return {
                "results": [
                    {"title": "source-1", "url": "https://example.com/1"},
                    {"title": "source-2", "url": "https://example.com/2"},
                ]
            }

    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr("app.agents.deepagents.TavilySearch", lambda **_: FakeTavily())

    search = build_tavily_search()

    with caplog.at_level("INFO"):
        result = await search.ainvoke({"query": "latest US retail trend"})

    assert len(result["results"]) == 2
    assert "web.search.start" in caplog.text
    assert "web.search.completed" in caplog.text
    assert "result_count=2" in caplog.text
