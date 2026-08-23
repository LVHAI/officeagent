from __future__ import annotations

from typing import Any


def _source_key(source: Any) -> tuple[str, str, str]:
    if isinstance(source, dict):
        return (
            str(source.get("kind", "")),
            str(source.get("uri", "")),
            str(source.get("title", "")),
        )
    return (str(getattr(source, "kind", "")), str(getattr(source, "uri", "")), str(getattr(source, "title", "")))


def aggregate_agent_outputs(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build deterministic, citation-aware context for the Report Agent."""
    successful: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    sources: list[Any] = []
    seen: set[tuple[str, str, str]] = set()

    for output in outputs:
        status = str(output.get("status", "unknown"))
        if status == "completed":
            successful.append(output)
        else:
            failed.append(output)
            if output.get("result") is not None:
                partial.append(output)
        for source in output.get("sources", []) or []:
            key = _source_key(source)
            if key not in seen:
                seen.add(key)
                sources.append(source)

    return {
        "successful_results": successful,
        "partial_results": partial,
        "failed_results": failed,
        "sources": sources,
        "has_partial_result": bool(failed),
    }
