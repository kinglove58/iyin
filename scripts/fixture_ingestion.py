"""Load the explicitly fictional research fixture through the production storage path."""

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from apps.api.afs.config import get_settings
from apps.api.afs.database import SessionLocal
from apps.api.afs.models import CandidateStatus, Chunk, Founder, Source, SourceCandidate
from services.content import content_hash, semantic_chunks
from services.providers import MockEmbeddingProvider
from services.storage import RawEvidenceStore
from sqlalchemy import select, text
from starlette.concurrency import run_in_threadpool

FIXTURE_URL = "https://example.test/fixtures/fictional-archivist"
FIXTURE_CANDIDATE_URL = "https://example.test/fixtures/fictional-archivist-follow-up"
FIXTURE_PATH = Path("fixtures/public-domain-research-fixture.md")


async def ingest() -> None:
    settings = get_settings()
    raw_bytes = await run_in_threadpool(FIXTURE_PATH.read_bytes)
    cleaned = raw_bytes.decode("utf-8").strip()
    digest = content_hash(cleaned)

    # The immutable original is written before any parsing or transformation.
    store = RawEvidenceStore(settings)
    await run_in_threadpool(store.ensure_bucket)
    stored = await run_in_threadpool(
        store.put_immutable, raw_bytes, "text/markdown", suffix="md"
    )

    async with SessionLocal() as db:
        founder = await db.scalar(select(Founder).where(Founder.slug == "fictional-archivist"))
        if founder is None:
            founder = Founder(
                slug="fictional-archivist",
                name="Fictional Archivist (test fixture)",
                collection_name="Deterministic Test Evidence",
                biography="An explicitly fictional identity used only for automated verification.",
                status="fixture-only-not-a-real-person",
            )
            db.add(founder)
            await db.flush()

        candidate = await db.scalar(
            select(SourceCandidate).where(SourceCandidate.normalized_url == FIXTURE_CANDIDATE_URL)
        )
        if candidate is None:
            db.add(
                SourceCandidate(
                    founder_id=founder.id,
                    original_url=FIXTURE_CANDIDATE_URL,
                    normalized_url=FIXTURE_CANDIDATE_URL,
                    title="Fictional archivist follow-up (review workflow fixture)",
                    publisher="Local verification fixture",
                    discovery_query="deterministic admin workflow verification",
                    content_type="web_page",
                    status=CandidateStatus.pending,
                    score=1,
                    score_breakdown={"fixture": 1},
                    robots_status="fixture_allowed",
                )
            )

        existing = await db.scalar(select(Source).where(Source.canonical_url == FIXTURE_URL))
        if existing:
            await db.commit()
            print(f"Fixture already ingested: source={existing.id} object={stored.object_key}")
            return

        artifact_id = uuid.uuid4()
        await db.execute(
            text(
                """INSERT INTO raw_artifacts
                (id, object_key, sha256, media_type, byte_size, immutable)
                VALUES (:id, :key, :sha256, 'text/markdown', :size, true)"""
            ),
            {"id": artifact_id, "key": stored.object_key, "sha256": stored.sha256, "size": stored.byte_size},
        )

        source = Source(
            founder_id=founder.id,
            canonical_url=FIXTURE_URL,
            original_url=FIXTURE_URL,
            title="Fictional archival interview (deterministic fixture)",
            publisher="Local verification fixture",
            author="Fictional Archivist",
            publication_date=None,
            accessed_at=datetime.now(UTC),
            content_type="text/markdown",
            source_tier="A",
            primary_or_secondary="primary",
            rights_status="local_test_fixture",
            approval_status="approved",
            speaker_verified=True,
            quality_score=1,
            relevance_score=1,
            authority_score=1,
            directness_score=1,
            recency_score=0,
            extraction_confidence=1,
            raw_artifact_id=artifact_id,
            content_hash=digest,
        )
        db.add(source)
        await db.flush()
        await db.execute(
            text("UPDATE raw_artifacts SET source_id=:source_id WHERE id=:id"),
            {"source_id": source.id, "id": artifact_id},
        )

        version_id = uuid.uuid4()
        await db.execute(
            text(
                """INSERT INTO source_versions
                (id, source_id, version, raw_artifact_id, cleaned_text, content_hash)
                VALUES (:id, :source_id, 1, :artifact_id, :cleaned, :hash)"""
            ),
            {
                "id": version_id,
                "source_id": source.id,
                "artifact_id": artifact_id,
                "cleaned": cleaned,
                "hash": digest,
            },
        )

        pieces = semantic_chunks(cleaned)
        vectors, _usage = await MockEmbeddingProvider(settings.embedding_dimensions).embed(
            [piece.text for piece in pieces]
        )
        for piece, vector in zip(pieces, vectors, strict=True):
            db.add(
                Chunk(
                    source_id=source.id,
                    source_version_id=version_id,
                    text=piece.text,
                    section_title=piece.section_title,
                    start_character=piece.start_character,
                    end_character=piece.end_character,
                    token_count=piece.token_count,
                    speaker_verified=True,
                    answer_eligible=True,
                    quality_flags=piece.quality_flags,
                    embedding=vector,
                    embedding_model=settings.embedding_model,
                    embedding_version="fixture-v1",
                )
            )
        await db.commit()
        print(
            f"Fixture ingested: source={source.id} chunks={len(pieces)} "
            f"sha256={stored.sha256} object={stored.object_key}"
        )


if __name__ == "__main__":
    asyncio.run(ingest())
