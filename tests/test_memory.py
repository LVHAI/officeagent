from datetime import datetime, timezone

from app.core.memory import LongTermMemory, build_short_term_context


def test_short_term_context_uses_recent_messages_and_summary() -> None:
    messages = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]

    context = build_short_term_context(messages, summary="Earlier the user asked about bags.", limit=2)

    assert context.summary == "Earlier the user asked about bags."
    assert [item["content"] for item in context.messages] == ["two", "three"]


def test_long_term_memory_key_is_stable_for_upsert() -> None:
    memory = LongTermMemory(
        memory_id="m1",
        user_id="u1",
        memory_type="preference",
        key="quotation_currency",
        value="USD",
        confidence=0.95,
        source_message_id="msg1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert memory.identity == ("u1", "preference", "quotation_currency")


def test_short_term_context_does_not_mutate_source_messages() -> None:
    messages = [{"role": "user", "content": "hello"}]
    original = [dict(messages[0])]

    build_short_term_context(messages, summary=None, limit=10)

    assert messages == original
