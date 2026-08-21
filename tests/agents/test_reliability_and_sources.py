import asyncio

import pytest

from app.agents.report_models import AnalysisReport
from app.agents.web import normalize_tavily_results
from app.core.reliability import CircuitBreaker, CircuitOpenError, retry_async


@pytest.mark.asyncio
async def test_retry_uses_exponential_backoff_and_eventually_succeeds(monkeypatch):
    calls = 0
    sleeps = []

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary")
        return "ok"

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    assert await retry_async(operation, attempts=3, base_delay=0.1) == "ok"
    assert calls == 3
    assert sleeps == [0.1, 0.2]


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)

    async def fail():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await retry_async(fail, attempts=1, breaker=breaker)
    with pytest.raises(RuntimeError):
        await retry_async(fail, attempts=1, breaker=breaker)
    with pytest.raises(CircuitOpenError):
        await retry_async(fail, attempts=1, breaker=breaker)


def test_tavily_results_are_normalized_for_audit():
    result = normalize_tavily_results({"results": [{"url": "https://example.com", "title": "Example"}]})
    assert result[0].url == "https://example.com"
    assert result[0].source == "tavily"
    assert result[0].retrieved_at


def test_analysis_report_is_structured():
    report = AnalysisReport(summary="summary", recommendations=["recommendation"])
    assert report.summary == "summary"
    assert report.recommendations == ["recommendation"]
