"""Authentication routes: login, logout, me (SPECS §19)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from ketrika.api.errors import UnauthorizedException
from ketrika.api.schemas import LoginRequest, LoginResponse, UserSummary
from ketrika.core.db import get_db
from ketrika.core.models.db import UserAccount

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
        secure=False,  # Set to True in HTTPS production
        max_age=720 * 60,
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
def logout(response: Response) -> dict[str, str]:
    """Clear session cookie."""
    response.delete_cookie(key="session_token")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserSummary)
def get_me(user: UserAccount = Depends(get_current_user)) -> UserSummary:
    """Return profile of currently authenticated user."""
    return UserSummary(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        disabled=user.disabled,
    )
