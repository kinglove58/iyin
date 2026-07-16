"""Import crawler discovery JSONL as pending, idempotent review candidates."""

import argparse
import asyncio
import json
from contextlib import suppress
from pathlib import Path
from typing import Any

from apps.api.afs.database import SessionLocal
from apps.api.afs.models import CandidateStatus, Founder, SourceCandidate
from services.scoring import CandidateSignals, score_candidate
from services.urls import normalize_url
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool


def parse_discovery_records(content: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in content.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("approval_status") != "pending" or not item.get("url") or not item.get("title"):
            continue
        records.append(item)
    return records


async def import_candidates(path: Path, founder_slug: str) -> tuple[int, int]:
    content = await run_in_threadpool(path.read_text, encoding="utf-8")
    records = parse_discovery_records(content)
    created = 0
    duplicates = 0
    async with SessionLocal() as db:
        founder = await db.scalar(select(Founder).where(Founder.slug == founder_slug))
        if founder is None:
            raise RuntimeError(f"Founder not found: {founder_slug}")
        for item in records:
            normalized = normalize_url(str(item["url"]), resolve_dns=False)
            exists = await db.scalar(
                select(SourceCandidate.id).where(SourceCandidate.normalized_url == normalized)
            )
            if exists:
                duplicates += 1
                continue
            published_year: int | None = None
            published_at = item.get("published_at")
            if isinstance(published_at, str) and len(published_at) >= 4:
                with suppress(ValueError):
                    published_year = int(published_at[:4])
            score, breakdown = score_candidate(
                CandidateSignals(
                    publisher_authority=0.6,
                    publication_year=published_year,
                    topic_relevance=0.8,
                    original_available=True,
                    extraction_feasibility=0.7,
                    source_transparency=0.8,
                )
            )
            db.add(
                SourceCandidate(
                    founder_id=founder.id,
                    original_url=str(item["url"]),
                    normalized_url=normalized,
                    title=str(item["title"])[:500],
                    publisher=str(item.get("publisher") or "YouTube")[:240],
                    discovery_query=str(item.get("discovery_query") or "")[:500] or None,
                    content_type=str(item.get("content_type") or "video")[:80],
                    status=CandidateStatus.pending,
                    score=score,
                    score_breakdown=breakdown,
                    robots_status="not_applicable_official_api_discovery",
                )
            )
            created += 1
        await db.commit()
    return created, duplicates


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--founder", default="iyinoluwa-aboyeji")
    args = parser.parse_args()
    created, duplicates = await import_candidates(args.file, args.founder)
    print(f"Discovery import complete: created={created} duplicates={duplicates}")


if __name__ == "__main__":
    asyncio.run(async_main())
