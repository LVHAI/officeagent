from datetime import datetime, timezone

from app.core.memory import LongTermMemory, build_short_term_context, extract_explicit_memories, render_long_term_memories


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
    memory = LongTermMemory("m1", "u1", "preference", "quotation_currency", "USD", 0.95, "msg1", datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert memory.identity == ("u1", "preference", "quotation_currency")


def test_short_term_context_does_not_mutate_source_messages() -> None:
    messages = [{"role": "user", "content": "hello"}]
    original = [dict(messages[0])]
    build_short_term_context(messages, summary=None, limit=10)
    assert messages == original


def test_explicit_memory_extraction_is_conservative() -> None:
    memories = extract_explicit_memories("u1", "msg1", "以后我的报价默认用美元")
    assert memories == [{"user_id": "u1", "memory_type": "preference", "key": "quotation_currency", "value": "USD", "confidence": 0.95, "source_message_id": "msg1"}]
    assert extract_explicit_memories("u1", "msg2", "我今天看了一个包") == []


def test_long_term_memory_can_be_rendered_for_context() -> None:
    now = datetime.now(timezone.utc)
    memory = LongTermMemory("m1", "u1", "preference", "quotation_currency", "USD", 0.95, "msg1", now, now)
    assert "preference.quotation_currency: USD" in render_long_term_memories([memory])
