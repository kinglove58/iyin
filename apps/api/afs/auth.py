import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_session
from .errors import AppError
from .models import Session, User

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, settings: Settings
) -> tuple[Session, str]:
    token = secrets.token_urlsafe(48)
    record = Session(
        user_id=user_id,
        token_hash=hash_session_token(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(record)
    await db.flush()
    return record, token


async def current_user(
    session_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_session),
) -> User | None:
    if not session_token:
        return None
    result = await db.execute(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(
            Session.token_hash == hash_session_token(session_token),
            Session.expires_at > datetime.now(UTC),
            User.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def require_admin(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise AppError(401, "authentication_required", "Administrator authentication is required")
    if not user.is_admin:
        raise AppError(403, "admin_required", "Administrator permission is required")
    return user


async def require_csrf(
    request: Request,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    session_token: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_session),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not session_token or not csrf_token:
        raise AppError(403, "csrf_required", "A valid CSRF token is required")
    result = await db.execute(
        select(Session).where(
            Session.token_hash == hash_session_token(session_token),
            Session.expires_at > datetime.now(UTC),
        )
    )
    record = result.scalar_one_or_none()
    if record is None or not secrets.compare_digest(record.csrf_token, csrf_token):
        raise AppError(403, "invalid_csrf", "The CSRF token is invalid")


AdminUser = Annotated[User, Depends(require_admin)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
