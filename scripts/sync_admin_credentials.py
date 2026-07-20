"""Synchronize the development administrator with current environment settings."""

import asyncio

from apps.api.afs.auth import hash_password
from apps.api.afs.config import get_settings
from apps.api.afs.database import SessionLocal
from apps.api.afs.models import Session, User
from sqlalchemy import delete, select


async def sync_admin_credentials() -> None:
    settings = get_settings()
    target_email = settings.admin_email.lower()
    async with SessionLocal() as db:
        admin = await db.scalar(select(User).where(User.email == target_email))
        if admin is None:
            existing_admins = list(
                (await db.scalars(select(User).where(User.is_admin.is_(True)))).all()
            )
            if len(existing_admins) != 1:
                raise RuntimeError(
                    "Cannot safely identify one existing administrator to synchronize."
                )
            admin = existing_admins[0]
            admin.email = target_email
        admin.password_hash = hash_password(settings.admin_password)
        admin.is_active = True
        admin.is_admin = True
        await db.execute(delete(Session).where(Session.user_id == admin.id))
        await db.commit()
    print("Administrator credentials synchronized and existing sessions revoked.")


if __name__ == "__main__":
    asyncio.run(sync_admin_credentials())
