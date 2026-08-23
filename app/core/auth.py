from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Cookie, HTTPException, status

from app.core.config import settings

SESSION_COOKIE = "officeagent_session"
SESSION_TTL = timedelta(days=7)


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    return _hash_password(password, secrets.token_bytes(16))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, _digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or int(rounds) != 310_000:
            return False
        return hmac.compare_digest(_hash_password(password, bytes.fromhex(salt_hex)), encoded)
    except (ValueError, TypeError):
        return False


def _dsn() -> str:
    return settings.postgres_dsn


def create_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("invalid email")
    now = datetime.now(timezone.utc)
    user_id = secrets.token_hex(16)
    with psycopg.connect(_dsn()) as conn:
        try:
            conn.execute("INSERT INTO users(user_id,email,password_hash,created_at,updated_at) VALUES (%s,%s,%s,%s,%s)", (user_id, email, hash_password(password), now, now))
            conn.commit()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            raise ValueError("email already registered") from None
    return {"user_id": user_id, "email": email}


def authenticate(email: str, password: str) -> dict | None:
    with psycopg.connect(_dsn()) as conn:
        row = conn.execute("SELECT user_id,email,password_hash FROM users WHERE email=%s", (email.strip().lower(),)).fetchone()
    if not row or not verify_password(password, row[2]):
        return None
    return {"user_id": row[0], "email": row[1]}


def create_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session_id = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expires_at = now + SESSION_TTL
    with psycopg.connect(_dsn()) as conn:
        conn.execute("INSERT INTO auth_sessions(session_id,token_hash,user_id,expires_at,created_at,last_used_at) VALUES (%s,%s,%s,%s,%s,%s)", (session_id, token_hash, user_id, expires_at, now, now))
        conn.commit()
    return token, expires_at


def get_user_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with psycopg.connect(_dsn()) as conn:
        row = conn.execute("SELECT u.user_id,u.email FROM auth_sessions s JOIN users u ON u.user_id=s.user_id WHERE s.token_hash=%s AND s.expires_at>%s", (token_hash, now)).fetchone()
        if row:
            conn.execute("UPDATE auth_sessions SET last_used_at=%s WHERE token_hash=%s", (now, token_hash))
            conn.commit()
    return {"user_id": row[0], "email": row[1]} if row else None


def delete_session(token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with psycopg.connect(_dsn()) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash=%s", (token_hash,))
        conn.commit()


def current_user(token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user
