import asyncio
import re

from apps.api.afs.auth import hash_password
from apps.api.afs.config import get_settings
from apps.api.afs.database import SessionLocal
from apps.api.afs.models import Founder, Topic, User
from sqlalchemy import select

TOPICS = [
    "Entrepreneurship", "Building in Africa", "Leadership", "Talent", "Hiring",
    "Team culture", "Fundraising", "Venture capital", "Product", "Sales", "Distribution",
    "Company building", "Failure", "Risk", "Faith", "Purpose", "Government", "Public policy",
    "Technology", "Artificial intelligence", "Education", "Economic development", "Diaspora",
    "Personal discipline", "Founder psychology", "Wealth creation", "Institution building",
    "JustBukIt application notes",
]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


async def seed() -> None:
    settings = get_settings()
    async with SessionLocal() as db:
        if not await db.scalar(select(Founder.id).where(Founder.slug == "iyinoluwa-aboyeji")):
            db.add(Founder(
                slug="iyinoluwa-aboyeji",
                name="Iyinoluwa Aboyeji",
                collection_name="The Iyinoluwa Aboyeji Public Ideas Collection",
                biography="A research index of approved public material. No quotations are seeded.",
                status="independent-not-endorsed",
            ))
        for name in TOPICS:
            if not await db.scalar(select(Topic.id).where(Topic.slug == slugify(name))):
                db.add(
                    Topic(
                        slug=slugify(name),
                        name=name,
                        description=f"Research evidence concerning {name.lower()}.",
                    )
                )
        if not await db.scalar(select(User.id).where(User.email == settings.admin_email.lower())):
            db.add(User(email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password),
                        display_name="Research Administrator", is_active=True, is_admin=True))
        await db.commit()
    print("Seed complete: founder metadata, topic taxonomy, and development administrator.")


if __name__ == "__main__":
    asyncio.run(seed())
