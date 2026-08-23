from __future__ import annotations

import json
from typing import Any

from app.agents.contracts import Source


def _source_key(source: Any) -> tuple[str, str, str]:
    if isinstance(source, dict):
        return (
            str(source.get("kind", "")),
            str(source.get("uri", "")),
            str(source.get("title", "")),
        )
    return (
        str(getattr(source, "kind", "")),
        str(getattr(source, "uri", "")),
        str(getattr(source, "title", "")),
    )


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def extract_sources(result: Any) -> list[Source]:
    """Extract normalized sources from AgentOutput results without inventing metadata."""
    found: list[Source] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            raw_sources = value.get("sources")
            if isinstance(raw_sources, list):
                for raw in raw_sources:
                    if not isinstance(raw, dict):
                        continue
                    if "document" in raw:
                        found.append(
                            Source(
                                kind="knowledge",
                                title=str(raw.get("document") or ""),
                                metadata={
                                    "page": raw.get("page"),
                                    "section": raw.get("section"),
                                    "article": raw.get("article"),
                                    "chunk_id": raw.get("chunk_id"),
                                    "score": raw.get("score"),
                                    "route": raw.get("route"),
                                },
                            )
                        )
                    elif raw.get("url") or raw.get("href"):
                        found.append(
                            Source(
                                kind="web",
                                title=str(raw.get("title") or ""),
                                uri=str(raw.get("url") or raw.get("href") or ""),
                                metadata={"content": raw.get("content", "")},
                            )
                        )
                    else:
                        found.append(
                            Source(
                                kind=str(raw.get("kind", "unknown")),
                                title=str(raw.get("title", "")),
                                uri=str(raw.get("uri", "")),
                                metadata=dict(raw.get("metadata", {})),
                            )
                        )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            parsed = _json_value(value)
            if parsed is not None and parsed is not value:
                visit(parsed)

    visit(result)
    unique: list[Source] = []
    seen: set[tuple[str, str, str]] = set()
    for source in found:
        key = _source_key(source)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def aggregate_agent_outputs(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build deterministic, citation-aware context for the Report Agent."""
    successful: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    sources: list[Source] = []
    seen: set[tuple[str, str, str]] = set()

    for output in outputs:
        status = str(output.get("status", "unknown"))
        if status == "completed":
            successful.append(output)
        else:
            failed.append(output)
            if output.get("result") is not None:
                partial.append(output)
        for source in [*output.get("sources", []), *extract_sources(output.get("result"))]:
            key = _source_key(source)
            if key not in seen:
                seen.add(key)
                sources.append(source)

    return {
        "successful_results": successful,
        "partial_results": partial,
        "failed_results": failed,
        "sources": [source.__dict__ for source in sources],
        "has_partial_result": bool(failed),
    }
