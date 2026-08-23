from app.agents.context_compression import compress_context


def test_small_context_is_not_compressed():
    result = compress_context({"answer": "ok"}, max_chars=100)
    assert result.method == "none"
    assert result.summary_llm_used is False


def test_structured_reduction_happens_before_truncation():
    value = {"answer": "keep this", "irrelevant": "x" * 5000, "sources": [{"chunk_id": "c1"}]}
    result = compress_context(value, max_chars=200)
    assert result.method in {"structured_reduce", "safe_truncate"}
    assert result.original_chars > result.compressed_chars


def test_summary_is_only_used_after_structured_reduction():
    calls = []

    def summary(text: str, limit: int) -> str:
        calls.append((text, limit))
        return "summary"

    value = {"answer": "x" * 1000, "sources": [{"chunk_id": "c1"}]}
    result = compress_context(value, max_chars=100, summary_fn=summary)
    assert result.method == "llm_summary"
    assert result.summary_llm_used is True
    assert calls


def test_summary_failure_falls_back_to_safe_truncation():
    def broken(_: str, __: int) -> str:
        raise RuntimeError("summary unavailable")

    result = compress_context({"answer": "x" * 1000}, max_chars=100, summary_fn=broken)
    assert result.method == "safe_truncate"
    assert result.fallback is True
    assert result.compressed_chars <= 100
