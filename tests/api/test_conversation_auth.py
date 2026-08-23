import pytest
from fastapi import HTTPException

from app.api import conversations


class FakeStore:
    def __init__(self):
        self.sessions = {"owned": {"session_id": "owned", "user_id": "user-a"}}

    def get_session(self, session_id):
        return self.sessions.get(session_id)


def test_owned_session_allows_owner(monkeypatch):
    monkeypatch.setattr(conversations, "_store", FakeStore())
    result = conversations._owned_session("owned", "user-a")
    assert result["user_id"] == "user-a"


def test_owned_session_rejects_other_user(monkeypatch):
    monkeypatch.setattr(conversations, "_store", FakeStore())
    with pytest.raises(HTTPException) as exc:
        conversations._owned_session("owned", "user-b")
    assert exc.value.status_code == 404


def test_owned_session_hides_missing_session(monkeypatch):
    monkeypatch.setattr(conversations, "_store", FakeStore())
    with pytest.raises(HTTPException) as exc:
        conversations._owned_session("missing", "user-a")
    assert exc.value.status_code == 404
