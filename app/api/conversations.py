from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.memory_store import PostgresMemoryStore

router = APIRouter(prefix="/api/v1")
_store = PostgresMemoryStore()


def configure_memory_store(store: PostgresMemoryStore) -> None:
    global _store
    _store = store


@router.get("/conversations/{session_id}/messages")
def get_conversation_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    messages = _store.list_messages(session_id, limit=limit, offset=offset)
    return {"session_id": session_id, "messages": messages, "limit": limit, "offset": offset}


@router.get("/users/{user_id}/memories")
def get_user_memories(user_id: str, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    memories = _store.list_long_term_memories(user_id, limit=limit)
    return {
        "user_id": user_id,
        "memories": [
            {
                "memory_id": item.memory_id,
                "memory_type": item.memory_type,
                "key": item.key,
                "value": item.value,
                "confidence": item.confidence,
                "source_message_id": item.source_message_id,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in memories
        ],
    }
