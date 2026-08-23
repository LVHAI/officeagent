from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import current_user
from app.core.memory_store import PostgresMemoryStore

router = APIRouter(prefix="/api/v1", tags=["conversations"])
_store = PostgresMemoryStore()


def configure_memory_store(store: PostgresMemoryStore) -> None:
    global _store
    _store = store


def _owned_session(session_id: str, user_id: str) -> dict:
    session = _store.get_session(session_id)
    if not session or session.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    return session


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)


@router.post("/conversations")
def create_conversation(request: CreateConversationRequest, user: dict = Depends(current_user)) -> dict:
    session_id = str(uuid4())
    _store.ensure_session(session_id, user["user_id"])
    return {"session_id": session_id, "user_id": user["user_id"], "title": request.title, "created": True}


@router.get("/conversations")
def list_conversations(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), user: dict = Depends(current_user)) -> dict:
    return {"conversations": _store.list_sessions(user_id=user["user_id"], limit=limit, offset=offset), "limit": limit, "offset": offset}


@router.get("/conversations/{session_id}")
def get_conversation(session_id: str, user: dict = Depends(current_user)) -> dict:
    return _owned_session(session_id, user["user_id"])


@router.get("/conversations/{session_id}/messages")
def get_conversation_messages(session_id: str, limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), user: dict = Depends(current_user)) -> dict:
    _owned_session(session_id, user["user_id"])
    return {"session_id": session_id, "messages": _store.list_messages(session_id, limit=limit, offset=offset), "limit": limit, "offset": offset}


@router.delete("/conversations/{session_id}")
def delete_conversation(session_id: str, user: dict = Depends(current_user)) -> dict:
    _owned_session(session_id, user["user_id"])
    _store.delete_session(session_id)
    return {"session_id": session_id, "deleted": True}


@router.get("/users/me/memories")
def get_user_memories(user: dict = Depends(current_user)) -> dict:
    memories = _store.list_long_term_memories(user["user_id"], limit=100)
    return {"user_id": user["user_id"], "memories": [{"memory_id": item.memory_id, "memory_type": item.memory_type, "key": item.key, "value": item.value, "confidence": item.confidence, "source_message_id": item.source_message_id, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()} for item in memories]}
