"""Authentication routes: login, logout, me (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.auth import (
    create_access_token,
    get_current_user,
    revoke_token,
    verify_password,
)
from ketrika.api.errors import UnauthorizedException
from ketrika.api.schemas import LoginRequest, LoginResponse, UserSummary
from ketrika.core.db import get_db
from ketrika.core.models.db import UserAccount
from ketrika.core.settings import get_settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate user with email and password, returning JWT token and setting session cookie."""
    stmt = select(UserAccount).where(UserAccount.email == payload.email)
    user = session.execute(stmt).scalar_one_or_none()

    if not user or user.disabled or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedException("Invalid email or password")

    token = create_access_token(user)

    # Set httpOnly cookie for web frontend
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "prod",
        max_age=get_settings().jwt_ttl_minutes * 60,
    )

    return LoginResponse(
        token=token,
        token_type="bearer",
        user=UserSummary(
            user_id=user.user_id,
            email=user.email,
            role=user.role,
            disabled=user.disabled,
        ),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(None, alias="session_token"),
    auth_header: str | None = Header(None, alias="Authorization"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Clear session cookie and actively revoke presented token (ADR-101 / R6.7)."""
    token_to_revoke = None
    if auth_header and auth_header.startswith("Bearer "):
        token_to_revoke = auth_header[7:].strip()
    elif session_token:
        token_to_revoke = session_token.strip()

    if token_to_revoke:
        try:
            revoke_token(token_to_revoke, session)
        except UnauthorizedException:
            # An invalid/expired token cannot authorise anything, including a new DB entry.
            token_to_revoke = None

    response.delete_cookie(key="session_token")
    return {"status": "logged_out", "revoked": bool(token_to_revoke)}


@router.get("/me", response_model=UserSummary)
def get_me(user: UserAccount = Depends(get_current_user)) -> UserSummary:
    """Return profile of currently authenticated user."""
    return UserSummary(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        disabled=user.disabled,
    )
