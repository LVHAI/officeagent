from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ShortTermContext:
    summary: str | None
    messages: list[dict[str, Any]]


@dataclass(frozen=True)
class LongTermMemory:
    memory_id: str
    user_id: str
    memory_type: str
    key: str
    value: str
    confidence: float
    source_message_id: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.user_id, self.memory_type, self.key


def build_short_term_context(
    messages: list[dict[str, Any]],
    *,
    summary: str | None,
    limit: int = 20,
) -> ShortTermContext:
    """Build bounded LLM context without changing the persisted raw messages."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return ShortTermContext(summary=summary, messages=[dict(item) for item in messages[-limit:]])


def render_short_term_context(context: ShortTermContext) -> str:
    parts: list[str] = []
    if context.summary:
        parts.append(f"[Conversation Summary]\n{context.summary}")
    if context.messages:
        lines = ["[Recent Conversation]"]
        for message in context.messages:
            role = str(message.get("role", "unknown"))
            content = str(message.get("content", ""))
            lines.append(f"{role}: {content}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def render_long_term_memories(memories: list[LongTermMemory]) -> str:
    if not memories:
        return ""
    lines = ["[Long-term User Memory]"]
    for memory in memories:
        lines.append(f"{memory.memory_type}.{memory.key}: {memory.value}")
    return "\n".join(lines)


def extract_explicit_memories(user_id: str, message_id: str, content: str) -> list[dict[str, Any]]:
    """Extract only explicit, high-confidence user preferences/facts.

    This deliberately avoids guessing. More advanced semantic extraction can be added
    later without changing the persistence model.
    """
    normalized = content.strip()
    lowered = normalized.lower()
    memories: list[dict[str, Any]] = []

    currency_markers = (
        ("默认用美元", "USD"),
        ("默认使用美元", "USD"),
        ("default currency is usd", "USD"),
        ("use usd by default", "USD"),
    )
    for marker, value in currency_markers:
        if marker in normalized or marker in lowered:
            memories.append(
                {
                    "user_id": user_id,
                    "memory_type": "preference",
                    "key": "quotation_currency",
                    "value": value,
                    "confidence": 0.95,
                    "source_message_id": message_id,
                }
            )
            break

    role_markers = (
        ("我负责采购", "采购"),
        ("我负责公司的采购", "采购"),
        ("i am responsible for procurement", "procurement"),
    )
    for marker, value in role_markers:
        if marker in normalized or marker in lowered:
            memories.append(
                {
                    "user_id": user_id,
                    "memory_type": "profile",
                    "key": "role",
                    "value": value,
                    "confidence": 0.95,
                    "source_message_id": message_id,
                }
            )
            break

    return memories
