from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompressionResult:
    value: Any
    original_chars: int
    compressed_chars: int
    method: str
    summary_llm_used: bool = False
    fallback: bool = False


def _chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 15)]}\n...[truncated]"


def _dedupe_list(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _structured_reduce(value: Any) -> Any:
    if isinstance(value, dict):
        reduced: dict[str, Any] = {}
        preferred = (
            "answer", "final_evidence", "summary", "result", "key_findings",
            "findings", "data", "content", "sources", "citations", "metadata",
        )
        for key in preferred:
            if key in value:
                reduced[key] = _structured_reduce(value[key])
        if not reduced:
            reduced = {str(key): _structured_reduce(item) for key, item in list(value.items())[:20]}
        return reduced
    if isinstance(value, list):
        return [_structured_reduce(item) for item in _dedupe_list(value[:30])]
    if isinstance(value, tuple):
        return [_structured_reduce(item) for item in _dedupe_list(list(value)[:30])]
    return value


def compress_context(
    value: Any,
    *,
    max_chars: int,
    summary_fn: Callable[[str, int], str] | None = None,
) -> CompressionResult:
    """Compress downstream context without changing the persisted/raw result.

    Structured reduction is always attempted first. An optional summary_fn is only
    used when the reduced value still exceeds max_chars. If it fails, safe truncation
    is returned so compression never becomes a workflow-fatal operation.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    original_chars = _chars(value)
    if original_chars <= max_chars:
        return CompressionResult(value, original_chars, original_chars, "none")

    reduced = _structured_reduce(value)
    reduced_chars = _chars(reduced)
    if reduced_chars <= max_chars:
        return CompressionResult(reduced, original_chars, reduced_chars, "structured_reduce")

    encoded = json.dumps(reduced, ensure_ascii=False, default=str)
    if summary_fn is not None:
        try:
            summary = summary_fn(encoded, max_chars)
            if isinstance(summary, str) and summary.strip():
                return CompressionResult(
                    summary,
                    original_chars,
                    len(summary),
                    "llm_summary",
                    summary_llm_used=True,
                )
        except Exception:
            pass

    fallback = _truncate(encoded, max_chars)
    return CompressionResult(
        fallback,
        original_chars,
        len(fallback),
        "safe_truncate",
        fallback=True,
    )
