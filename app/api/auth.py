from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.auth import SESSION_COOKIE, authenticate, create_session, create_user, current_user, delete_session
from app.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: AuthRequest) -> dict:
    try:
        return create_user(request.email, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login")
def login(request: AuthRequest, response: Response) -> dict:
    user = authenticate(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid email or password")
    token, expires_at = create_session(user["user_id"])
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=settings.environment == "production", expires=expires_at)
    return {**user, "expires_at": expires_at.isoformat()}


@router.post("/logout")
def logout(response: Response, token: str | None = Cookie(default=None, alias=SESSION_COOKIE), user: dict = Depends(current_user)) -> dict:
    delete_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True, "user_id": user["user_id"]}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user
