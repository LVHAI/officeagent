import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.deepagents import build_tavily_search


@pytest.mark.asyncio
async def test_tavily_search_wrapper_logs_and_preserves_sources(caplog):
    caplog.set_level(logging.INFO)
    tavily = Mock()
    tavily.ainvoke = AsyncMock(
        return_value=[
            {"title": "US Retail Outlook", "url": "https://example.com/retail", "content": "trend"}
        ]
    )

    with patch("app.agents.deepagents.TavilySearch", return_value=tavily), patch(
        "app.agents.deepagents.settings.tavily_api_key", "test-key"
    ):
        tool = build_tavily_search()
        result = await tool.ainvoke({"query": "US retail trends"})

    assert result[0]["url"] == "https://example.com/retail"
    messages = [record.getMessage() for record in caplog.records]
    assert any("web.search.start" in message for message in messages)
    assert any("web.search.completed" in message for message in messages)


def test_tavily_search_is_not_created_without_api_key():
    with patch("app.agents.deepagents.settings.tavily_api_key", None):
        assert build_tavily_search() is None
