from __future__ import annotations

import json
from typing import Any

from app.agents.context_compression import compress_context
from app.agents.contracts import Source

# Report context is deliberately much smaller than the raw AgentOutput. The full
# output remains in LangGraph state for trace/audit; only concise evidence crosses
# the Report Agent boundary.
REPORT_RESULT_MAX_CHARS = 2500
REPORT_SOURCE_CONTENT_MAX_CHARS = 600


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


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n...[truncated]"


def _message_content(message: Any) -> str | None:
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    return None


def compact_result_for_report(result: Any, limit: int = REPORT_RESULT_MAX_CHARS) -> Any:
    """Keep concise final evidence and never forward raw agent message history."""
    compressed = compress_context(result, max_chars=limit)
    return compressed.value


def _compact_source(source: Any) -> dict[str, Any]:
    if isinstance(source, Source):
        kind = source.kind
        title = source.title
        uri = source.uri
        metadata = dict(source.metadata)
    elif isinstance(source, dict):
        kind = str(source.get("kind", "unknown"))
        title = str(source.get("title", ""))
        uri = str(source.get("uri", ""))
        metadata = dict(source.get("metadata", {}))
    else:
        kind = str(getattr(source, "kind", "unknown"))
        title = str(getattr(source, "title", ""))
        uri = str(getattr(source, "uri", ""))
        metadata = dict(getattr(source, "metadata", {}) or {})

    if "content" in metadata:
        metadata["content"] = _truncate_text(str(metadata["content"]), REPORT_SOURCE_CONTENT_MAX_CHARS)
    return {"kind": kind, "title": title, "uri": uri, "metadata": metadata}


def _compact_output(output: dict[str, Any]) -> dict[str, Any]:
    """Keep only the Agent Contract fields required by downstream synthesis."""
    return {
        "agent_id": output.get("agent_id"),
        "status": output.get("status"),
        "result": compact_result_for_report(output.get("result")),
        "sources": [_compact_source(source) for source in output.get("sources", [])],
        "errors": output.get("errors", []),
    }


def _knowledge_source(raw: dict[str, Any]) -> Source:
    metadata = {
        "document_id": raw.get("document_id"),
        "page": raw.get("page"),
        "section": raw.get("section"),
        "article": raw.get("article"),
        "chunk_id": raw.get("chunk_id"),
        "parent_id": raw.get("parent_id"),
        "chunk_type": raw.get("chunk_type"),
        "score": raw.get("score"),
        "route": raw.get("route"),
    }
    return Source(
        kind="knowledge",
        title=str(raw.get("document") or ""),
        uri=str(raw.get("uri") or ""),
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


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
                    if "document" in raw and not (raw.get("url") or raw.get("href")):
                        found.append(_knowledge_source(raw))
                    elif raw.get("url") or raw.get("href"):
                        found.append(
                            Source(
                                kind="web",
                                title=str(raw.get("title") or ""),
                                uri=str(raw.get("url") or raw.get("href") or ""),
                                metadata={
                                    "content": _truncate_text(
                                        str(raw.get("content", "")),
                                        REPORT_SOURCE_CONTENT_MAX_CHARS,
                                    )
                                },
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
    """Build deterministic, citation-aware and token-bounded synthesis context."""
    successful: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    sources: list[Source] = []
    seen: set[tuple[str, str, str]] = set()

    for output in outputs:
        status = str(output.get("status", "unknown"))
        compact = _compact_output(output)
        if status == "completed":
            successful.append(compact)
        else:
            failed.append(compact)
            if output.get("result") is not None:
                partial.append(compact)
        for source in [*output.get("sources", []), *extract_sources(output.get("result"))]:
            key = _source_key(source)
            if key not in seen:
                seen.add(key)
                sources.append(source)

    return {
        "successful_results": successful,
        "partial_results": partial,
        "failed_results": failed,
        "sources": [_compact_source(source) for source in sources],
        "has_partial_result": bool(failed),
    }
