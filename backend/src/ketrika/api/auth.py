"""Authentication and authorization utilities for Ketrika API (SPECS §19)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.errors import ForbiddenException, UnauthorizedException
from ketrika.core.db import get_db
from ketrika.core.models.db import ApiKey, UserAccount
from ketrika.core.settings import get_settings

password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2 hash."""
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(user: UserAccount, expires_delta: timedelta | None = None) -> str:
    """Create signed JWT access token."""
    settings = get_settings()
    ttl = expires_delta or timedelta(minutes=settings.jwt_ttl_minutes)
    expire = datetime.now(UTC) + ttl
    payload: dict[str, Any] = {
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(UTC).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Session has expired") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException("Invalid authentication token") from e


def generate_api_key_pair() -> tuple[str, str, str]:
    """Generate raw API key, prefix, and argon2 hash.

    Format: ketrika_live_<32 random hex chars>
    """
    secret_part = secrets.token_hex(16)
    raw_key = f"ketrika_live_{secret_part}"
    prefix = raw_key[:16]
    key_hash = hash_password(raw_key)
    return raw_key, prefix, key_hash


def create_api_key_for_user(session: Session, user: UserAccount) -> tuple[str, ApiKey]:
    """Create and persist a new API key for given user, returning (raw_key, ApiKey)."""
    raw_key, prefix, key_hash = generate_api_key_pair()
    api_key_obj = ApiKey(
        api_key_id=uuid.uuid4(),
        user_id=user.user_id,
        prefix=prefix,
        key_hash=key_hash,
        created_at=datetime.now(UTC),
    )
    session.add(api_key_obj)
    session.flush()
    return raw_key, api_key_obj


def authenticate_api_key(raw_key: str, session: Session) -> UserAccount | None:
    """Authenticate via X-API-Key header against argon2 key hashes."""
    if not raw_key.startswith("ketrika_live_"):
        return None

    prefix = raw_key[:16]
    stmt = (
        select(ApiKey)
        .where(ApiKey.prefix == prefix, ApiKey.revoked_at.is_(None))
        .join(UserAccount)
        .where(UserAccount.disabled.is_(False))
    )
    candidates = list(session.execute(stmt).scalars().all())

    for candidate in candidates:
        if verify_password(raw_key, candidate.key_hash):
            candidate.last_used_at = datetime.now(UTC)
            session.flush()
            return candidate.user

    return None


def get_current_user(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    session_token: str | None = Cookie(None, alias="session_token"),
    session: Session = Depends(get_db),
) -> UserAccount:
    """FastAPI dependency: Extract and authenticate current user from API key, cookie, or Bearer header."""
    # 1. Check X-API-Key header
    if x_api_key:
        user = authenticate_api_key(x_api_key, session)
        if user:
            return user
        raise UnauthorizedException("Invalid or revoked API key")

    # 2. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    token: str | None = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif session_token:
        token = session_token

    if not token:
        raise UnauthorizedException("Authentication required")

    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token payload")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as e:
        raise UnauthorizedException("Invalid user ID in token") from e

    user = session.get(UserAccount, user_uuid)
    if not user or user.disabled:
        raise UnauthorizedException("User not found or disabled")

    return user


def require_admin(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    """Dependency requiring user to have admin role."""
    if user.role != "admin":
        raise ForbiddenException("Administrator privileges required")
    return user


def require_client(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    """Dependency requiring user to have at least client role."""
    if user.role not in ("admin", "client"):
        raise ForbiddenException("Access denied")
    return user


def ensure_demo_admin(session: Session) -> UserAccount:
    """Ensure default demo administrator exists in auth.user_account."""
    settings = get_settings()
    stmt = select(UserAccount).where(UserAccount.email == settings.demo_admin_email)
    admin = session.execute(stmt).scalar_one_or_none()

    if admin is None:
        admin = UserAccount(
            user_id=uuid.uuid4(),
            email=settings.demo_admin_email,
            password_hash=hash_password(settings.demo_admin_password),
            role="admin",
            disabled=False,
            created_at=datetime.now(UTC),
        )
        session.add(admin)
        session.commit()
    return admin
