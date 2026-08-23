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
        expected = _hash_password(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(expected, encoded)
    except (ValueError, TypeError):
        return False


def _dsn() -> str:
    return settings.postgres_dsn


def setup_auth_store() -> None:
    with psycopg.connect(_dsn()) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS auth_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)")
        conn.commit()


def create_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("invalid email")
    password_hash = hash_password(password)
    now = datetime.now(timezone.utc)
    user_id = str(secrets.token_hex(16))
    with psycopg.connect(_dsn()) as conn:
        try:
            conn.execute("INSERT INTO users(user_id, email, password_hash, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)", (user_id, email, password_hash, now, now))
            conn.commit()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            raise ValueError("email already registered") from None
    return {"user_id": user_id, "email": email}


def authenticate(email: str, password: str) -> dict | None:
    with psycopg.connect(_dsn()) as conn:
        row = conn.execute("SELECT user_id, email, password_hash FROM users WHERE email = %s", (email.strip().lower(),)).fetchone()
    if not row or not verify_password(password, row[2]):
        return None
    return {"user_id": row[0], "email": row[1]}


def create_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    with psycopg.connect(_dsn()) as conn:
        conn.execute("INSERT INTO auth_sessions(token_hash, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)", (token_hash, user_id, expires_at, datetime.now(timezone.utc)))
        conn.commit()
    return token, expires_at


def get_user_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with psycopg.connect(_dsn()) as conn:
        row = conn.execute("SELECT u.user_id, u.email FROM auth_sessions s JOIN users u ON u.user_id = s.user_id WHERE s.token_hash = %s AND s.expires_at > %s", (token_hash, now)).fetchone()
    return {"user_id": row[0], "email": row[1]} if row else None


def delete_session(token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with psycopg.connect(_dsn()) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (token_hash,))
        conn.commit()


def current_user(token: str | None = None) -> dict:
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user
