# mypy: disable-error-code="untyped-decorator"

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from celery import Task
from services.content import content_hash, prompt_injection_flags, semantic_chunks
from services.providers import (
    GeminiTranscriptCleanupProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    OpenAITranscriptCleanupProvider,
    ProviderUsage,
)
from services.scoring import CandidateSignals, score_candidate
from services.storage import RawEvidenceStore
from services.urls import normalize_url
from services.youtube_ingestion import (
    caption_chunks,
    fetch_public_caption_segments,
    fetch_zyte_caption_segments,
)

from apps.api.afs.config import get_settings
from apps.api.afs.models import (
    BackgroundJob,
    Chunk,
    InterviewTurnSuggestion,
    JobStatus,
    Source,
)

from .celery_app import celery_app


class RetryingTask(Task):  # type: ignore[misc]
    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = 5


@celery_app.task(base=RetryingTask, name="afs.discovery.score_candidate")
def score_candidate_task(url: str, signals: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_url(url, resolve_dns=True)
    score, breakdown = score_candidate(CandidateSignals(**signals))
    return {"normalized_url": normalized, "score": score, "score_breakdown": breakdown}


@celery_app.task(base=RetryingTask, name="afs.crawl.store_snapshot")
def store_snapshot(data: str, media_type: str = "text/html") -> dict[str, Any]:
    settings = get_settings()
    stored = RawEvidenceStore(settings).put_immutable(data.encode(), media_type, suffix="html")
    return {
        "object_key": stored.object_key,
        "sha256": stored.sha256,
        "byte_size": stored.byte_size,
        "created": stored.created,
    }


@celery_app.task(base=RetryingTask, name="afs.ingestion.clean_and_chunk")
def clean_and_chunk(content: str) -> dict[str, Any]:
    chunks = semantic_chunks(content)
    return {
        "content_hash": content_hash(content),
        "quality_flags": prompt_injection_flags(content),
        "chunks": [
            {
                "text": item.text,
                "section_title": item.section_title,
                "start_character": item.start_character,
                "end_character": item.end_character,
                "token_count": item.token_count,
                "quality_flags": item.quality_flags,
            }
            for item in chunks
        ],
    }


def _safe_error(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc)).strip()[:1000] or type(exc).__name__


async def _set_ingestion_failure(job_id: uuid.UUID, message: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is not None:
                job.status = JobStatus.failed
                job.progress = 100
                job.finished_at = datetime.now(UTC)
                job.error_details = message
                await db.commit()
    finally:
        await engine.dispose()


async def _process_approved_source(job_id: uuid.UUID) -> dict[str, Any]:
    import asyncio

    from sqlalchemy import func, select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                raise ValueError("The ingestion job no longer exists")
            if job.status == JobStatus.cancelled:
                return {"status": "cancelled", "job_id": str(job.id)}
            use_zyte_proxy = bool(job.payload.get("use_zyte_proxy"))
            if not use_zyte_proxy:
                recent_ip_blocks = await db.scalar(
                    select(func.count())
                    .select_from(BackgroundJob)
                    .where(
                        BackgroundJob.job_type == "youtube_caption_ingestion",
                        BackgroundJob.status == JobStatus.failed,
                        BackgroundJob.finished_at > datetime.now(UTC) - timedelta(minutes=30),
                        BackgroundJob.error_details.ilike("%blocking requests from your IP%"),
                    )
                )
                if (recent_ip_blocks or 0) >= 3:
                    job.status = JobStatus.cancelled
                    job.progress = 0
                    job.finished_at = datetime.now(UTC)
                    job.error_details = (
                        "Deferred because YouTube temporarily blocked repeated caption "
                        "requests. Retry after the cooldown."
                    )
                    await db.commit()
                    return {"status": "cancelled", "job_id": str(job.id)}
            source_id = uuid.UUID(str(job.payload["source_id"]))
            source = await db.get(Source, source_id)
            if source is None:
                raise ValueError("The approved source no longer exists")
            job.status = JobStatus.running
            job.progress = 5
            job.attempts += 1
            job.started_at = datetime.now(UTC)
            job.error_details = None
            await db.commit()

            existing_chunks = await db.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.source_id == source.id)
            )
            if existing_chunks:
                job.status = JobStatus.succeeded
                job.progress = 100
                job.finished_at = datetime.now(UTC)
                job.payload = {**job.payload, "result": "already_processed"}
                await db.commit()
                return {"status": "already_processed", "source_id": str(source.id)}

            if use_zyte_proxy:
                if not settings.zyte_api_key:
                    raise ValueError("Zyte API credentials are not configured")
                configured_request_cap = job.payload.get("max_zyte_requests")
                max_zyte_requests = (
                    configured_request_cap
                    if isinstance(configured_request_cap, int)
                    else settings.max_zyte_requests_per_video
                )
                caption_fetch = await asyncio.to_thread(
                    fetch_zyte_caption_segments,
                    source.canonical_url,
                    settings.zyte_api_key,
                    max_zyte_requests,
                )
            else:
                caption_fetch = await asyncio.to_thread(
                    fetch_public_caption_segments,
                    source.canonical_url,
                )
            pieces = caption_chunks(caption_fetch.segments)
            if not pieces:
                raise ValueError("The public caption track did not produce any evidence chunks")
            job.progress = 35
            await db.commit()

            store = RawEvidenceStore(settings)
            await asyncio.to_thread(store.ensure_bucket)
            stored = await asyncio.to_thread(
                store.put_immutable,
                caption_fetch.raw_bytes,
                "application/json",
                suffix="youtube-captions.json",
            )
            vectors, usage = await MockEmbeddingProvider(settings.embedding_dimensions).embed(
                [piece.text for piece in pieces]
            )
            job.progress = 65
            await db.commit()

            artifact_id = uuid.uuid4()
            version_id = uuid.uuid4()
            media_asset_id = uuid.uuid4()
            transcript_id = uuid.uuid4()
            digest = content_hash(
                " ".join(segment.text for segment in caption_fetch.segments)
            )
            cleaned_text = "\n".join(
                segment.text for segment in caption_fetch.segments
            )
            next_version = (
                await db.scalar(
                    text(
                        "SELECT COALESCE(MAX(version), 0) + 1 "
                        "FROM source_versions WHERE source_id=:source_id"
                    ),
                    {"source_id": source.id},
                )
                or 1
            )
            await db.execute(
                text(
                    """INSERT INTO raw_artifacts
                    (id, source_id, object_key, sha256, media_type, byte_size, immutable)
                    VALUES (:id, :source_id, :key, :sha256, :media_type, :size, true)"""
                ),
                {
                    "id": artifact_id,
                    "source_id": source.id,
                    "key": stored.object_key,
                    "sha256": stored.sha256,
                    "media_type": "application/json",
                    "size": stored.byte_size,
                },
            )
            await db.execute(
                text(
                    """INSERT INTO source_versions
                    (id, source_id, version, raw_artifact_id, cleaned_text, content_hash)
                    VALUES (:id, :source_id, :version, :artifact_id, :cleaned, :hash)"""
                ),
                {
                    "id": version_id,
                    "source_id": source.id,
                    "version": next_version,
                    "artifact_id": artifact_id,
                    "cleaned": cleaned_text,
                    "hash": digest,
                },
            )
            await db.execute(
                text(
                    """INSERT INTO media_assets
                    (id, source_id, platform, platform_id, metadata)
                    VALUES (:id, :source_id, 'youtube', :video_id, CAST(:metadata AS jsonb))"""
                ),
                {
                    "id": media_asset_id,
                    "source_id": source.id,
                    "video_id": caption_fetch.video_id,
                    "metadata": json.dumps(
                        {
                            "caption_language": caption_fetch.language,
                            "automatically_generated": caption_fetch.is_generated,
                            "caption_pathway": caption_fetch.pathway,
                            "zyte_proxy_requests": caption_fetch.proxy_requests,
                        }
                    ),
                },
            )
            await db.execute(
                text(
                    """INSERT INTO transcripts
                    (id, source_id, media_asset_id, pathway, language, review_status)
                    VALUES (:id, :source_id, :media_asset_id, :pathway,
                    :language, 'pending')"""
                ),
                {
                    "id": transcript_id,
                    "source_id": source.id,
                    "media_asset_id": media_asset_id,
                    "pathway": caption_fetch.pathway,
                    "language": caption_fetch.language,
                },
            )
            await db.execute(
                text(
                    """INSERT INTO transcript_segments
                    (id, transcript_id, start_seconds, end_seconds, text,
                    transcription_confidence, review_status)
                    VALUES (:id, :transcript_id, :start_seconds, :end_seconds, :text,
                    :confidence, 'pending')"""
                ),
                [
                    {
                        "id": uuid.uuid4(),
                        "transcript_id": transcript_id,
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                        "text": segment.text,
                        "confidence": 0.7 if caption_fetch.is_generated else 0.9,
                    }
                    for segment in caption_fetch.segments
                ],
            )
            for piece, vector in zip(pieces, vectors, strict=True):
                db.add(
                    Chunk(
                        source_id=source.id,
                        source_version_id=version_id,
                        text=piece.text,
                        start_seconds=piece.start_seconds,
                        end_seconds=piece.end_seconds,
                        token_count=piece.token_count,
                        speaker_verified=False,
                        answer_eligible=False,
                        quality_flags=piece.quality_flags,
                        embedding=vector,
                        embedding_model=usage.model,
                        embedding_version="youtube-caption-v1",
                    )
                )
            source.accessed_at = datetime.now(UTC)
            source.content_type = "transcript"
            source.language = caption_fetch.language
            source.rights_status = "public_caption_pending_speaker_review"
            source.extraction_confidence = (
                0.7 if caption_fetch.is_generated else 0.9
            )
            source.raw_artifact_id = artifact_id
            source.content_hash = digest
            job.status = JobStatus.succeeded
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            job.payload = {
                **job.payload,
                "video_id": caption_fetch.video_id,
                "caption_language": caption_fetch.language,
                "automatically_generated": caption_fetch.is_generated,
                "chunk_count": len(pieces),
                "segment_count": len(caption_fetch.segments),
                "speaker_review_required": True,
                "embedding_provider": usage.provider,
                "embedding_cost_usd": usage.estimated_cost_usd,
                "caption_pathway": caption_fetch.pathway,
                "zyte_proxy_requests": caption_fetch.proxy_requests,
                "estimated_zyte_cost_usd": (
                    settings.zyte_caption_estimated_cost_per_video
                    if use_zyte_proxy
                    else 0
                ),
            }
            await db.commit()
            return {
                "status": "succeeded",
                "source_id": str(source.id),
                "chunk_count": len(pieces),
                "speaker_review_required": True,
            }
    finally:
        await engine.dispose()


@celery_app.task(
    base=RetryingTask,
    name="afs.ingestion.process_approved_source",
    rate_limit="10/m",
)
def process_approved_source(job_id: str) -> dict[str, Any]:
    import asyncio

    parsed_job_id = uuid.UUID(job_id)
    try:
        return asyncio.run(_process_approved_source(parsed_job_id))
    except Exception as exc:
        message = _safe_error(exc)
        asyncio.run(_set_ingestion_failure(parsed_job_id, message))
        return {"status": "failed", "job_id": job_id, "error": message}


@celery_app.task(base=RetryingTask, name="afs.ai.embed_batch")
def embed_batch(texts: list[str]) -> dict[str, Any]:
    import asyncio

    settings = get_settings()
    vectors, usage = asyncio.run(MockEmbeddingProvider(settings.embedding_dimensions).embed(texts))
    return {
        "vectors": vectors,
        "input_tokens": usage.input_tokens,
        "estimated_cost_usd": usage.estimated_cost_usd,
        "provider": usage.provider,
        "model": usage.model,
        "is_mock": usage.is_mock,
        "idempotency_key": hashlib.sha256("\n".join(texts).encode()).hexdigest(),
    }


async def _clean_verified_sources(job_id: uuid.UUID) -> dict[str, Any]:
    import time

    from sqlalchemy import select, text, update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    cleaner = OpenAITranscriptCleanupProvider(
        settings.openai_api_key,
        settings.extraction_model,
        settings.openai_extraction_input_cost_per_million,
        settings.openai_extraction_output_cost_per_million,
    )
    embedder = OpenAIEmbeddingProvider(
        settings.openai_api_key,
        settings.embedding_model,
        settings.embedding_dimensions,
        settings.openai_embedding_cost_per_million,
    )
    try:
        async with session_factory() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                raise ValueError("The cleanup job no longer exists")
            job.status = JobStatus.running
            job.started_at = datetime.now(UTC)
            job.progress = 1
            job.attempts += 1
            await db.commit()
            raw_limit = job.payload.get("limit", 50)
            limit = raw_limit if isinstance(raw_limit, int) else 50
            source_ids = list(
                (
                    await db.scalars(
                        select(Chunk.source_id)
                        .join(Source, Source.id == Chunk.source_id)
                        .where(
                            Source.speaker_verified.is_(True),
                            Chunk.answer_eligible.is_(True),
                            Chunk.embedding_version == "youtube-caption-v1",
                        )
                        .distinct()
                        .limit(limit)
                    )
                ).all()
            )
            completed = 0
            total_cost = 0.0
            for source_id in source_ids:
                if job.cancel_requested:
                    job.status = JobStatus.cancelled
                    break
                monthly_cost = float(
                    await db.scalar(
                        text(
                            """
                            SELECT COALESCE(SUM(estimated_cost_usd), 0)
                            FROM provider_cost_records
                            WHERE provider = 'openai'
                              AND created_at >= date_trunc('month', now())
                            """
                        )
                    )
                    or 0
                )
                if monthly_cost >= settings.max_monthly_ai_cost:
                    raise ValueError("The configured monthly AI cost limit has been reached")
                source = await db.get(Source, source_id)
                if source is None:
                    continue
                old_chunks = list(
                    (
                        await db.scalars(
                            select(Chunk)
                            .where(
                                Chunk.source_id == source_id,
                                Chunk.answer_eligible.is_(True),
                                Chunk.embedding_version == "youtube-caption-v1",
                            )
                            .order_by(Chunk.start_seconds.nulls_first(), Chunk.created_at)
                        )
                    ).all()
                )
                if not old_chunks:
                    continue
                cleanup_started = time.perf_counter()
                cleanup_input = [
                    {"chunk_id": str(chunk.id), "text": chunk.text}
                    for chunk in old_chunks
                ]
                try:
                    cleaned_rows, cleanup_usage = await cleaner.clean_chunks(
                        source.title,
                        cleanup_input,
                    )
                except ValueError:
                    cleaned_rows = []
                    cleanup_usages = []
                    for item in cleanup_input:
                        cleaned_batch, batch_usage = await cleaner.clean_chunks(
                            source.title,
                            [item],
                        )
                        cleaned_rows.extend(cleaned_batch)
                        cleanup_usages.append(batch_usage)
                    first_usage = cleanup_usages[0]
                    cleanup_usage = ProviderUsage(
                        input_tokens=sum(item.input_tokens for item in cleanup_usages),
                        output_tokens=sum(item.output_tokens for item in cleanup_usages),
                        estimated_cost_usd=sum(
                            item.estimated_cost_usd for item in cleanup_usages
                        ),
                        provider=first_usage.provider,
                        model=first_usage.model,
                        is_mock=first_usage.is_mock,
                    )
                cleaned_by_id = {
                    uuid.UUID(item["chunk_id"]): item["cleaned_text"]
                    for item in cleaned_rows
                }
                cleaned_texts = [cleaned_by_id[chunk.id] for chunk in old_chunks]
                vectors, embedding_usage = await embedder.embed(cleaned_texts)
                cleanup_latency_ms = round((time.perf_counter() - cleanup_started) * 1000)
                next_version = (
                    await db.scalar(
                        text(
                            "SELECT COALESCE(MAX(version), 0) + 1 "
                            "FROM source_versions WHERE source_id=:source_id"
                        ),
                        {"source_id": source_id},
                    )
                    or 1
                )
                version_id = uuid.uuid4()
                joined_text = "\n\n".join(cleaned_texts)
                await db.execute(
                    text(
                        """
                        INSERT INTO source_versions
                            (id, source_id, version, raw_artifact_id, cleaned_text, content_hash)
                        VALUES
                            (:id, :source_id, :version, :raw_artifact_id, :cleaned_text, :content_hash)
                        """
                    ),
                    {
                        "id": version_id,
                        "source_id": source_id,
                        "version": next_version,
                        "raw_artifact_id": source.raw_artifact_id,
                        "cleaned_text": joined_text,
                        "content_hash": content_hash(joined_text),
                    },
                )
                for old_chunk, cleaned_text, vector in zip(
                    old_chunks, cleaned_texts, vectors, strict=True
                ):
                    db.add(
                        Chunk(
                            source_id=old_chunk.source_id,
                            source_version_id=version_id,
                            speaker_id=old_chunk.speaker_id,
                            text=cleaned_text,
                            context_before=old_chunk.context_before,
                            context_after=old_chunk.context_after,
                            section_title=old_chunk.section_title,
                            start_character=old_chunk.start_character,
                            end_character=old_chunk.end_character,
                            start_seconds=old_chunk.start_seconds,
                            end_seconds=old_chunk.end_seconds,
                            token_count=max(1, round(len(cleaned_text.split()) * 1.3)),
                            speaker_verified=True,
                            answer_eligible=not bool(old_chunk.quality_flags),
                            quality_flags=old_chunk.quality_flags,
                            embedding=vector,
                            embedding_model=embedding_usage.model,
                            embedding_version="openai-cleaned-v1",
                        )
                    )
                await db.execute(
                    update(Chunk)
                    .where(Chunk.id.in_([chunk.id for chunk in old_chunks]))
                    .values(answer_eligible=False)
                )
                for usage, operation in (
                    (cleanup_usage, "transcript_cleanup"),
                    (embedding_usage, "evidence_embedding"),
                ):
                    await db.execute(
                        text(
                            """
                            INSERT INTO api_usage_records
                                (provider, operation, tokens_in, tokens_out, latency_ms, correlation_id)
                            VALUES
                                (:provider, :operation, :tokens_in, :tokens_out, :latency_ms, :correlation_id)
                            """
                        ),
                        {
                            "provider": usage.provider,
                            "operation": operation,
                            "tokens_in": usage.input_tokens,
                            "tokens_out": usage.output_tokens,
                            "latency_ms": cleanup_latency_ms,
                            "correlation_id": job.correlation_id,
                        },
                    )
                    await db.execute(
                        text(
                            """
                            INSERT INTO provider_cost_records
                                (provider, operation, units, estimated_cost_usd, job_id)
                            VALUES
                                (:provider, :operation, :units, :cost, :job_id)
                            """
                        ),
                        {
                            "provider": usage.provider,
                            "operation": operation,
                            "units": usage.input_tokens + usage.output_tokens,
                            "cost": usage.estimated_cost_usd,
                            "job_id": job.id,
                        },
                    )
                    total_cost += usage.estimated_cost_usd
                completed += 1
                job.progress = max(1, round(completed / max(1, len(source_ids)) * 100))
                job.payload = {
                    **job.payload,
                    "completed_source_count": completed,
                    "estimated_openai_cost_usd": round(total_cost, 6),
                }
                await db.commit()
            if job.status != JobStatus.cancelled:
                job.status = JobStatus.succeeded
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            job.payload = {
                **job.payload,
                "completed_source_count": completed,
                "estimated_openai_cost_usd": round(total_cost, 6),
            }
            await db.commit()
            return {
                "status": job.status.value,
                "completed_source_count": completed,
                "estimated_openai_cost_usd": round(total_cost, 6),
            }
    finally:
        await engine.dispose()


@celery_app.task(
    base=RetryingTask,
    name="afs.ai.clean_verified_sources",
    rate_limit="10/m",
)
def clean_verified_sources_task(job_id: str) -> dict[str, Any]:
    import asyncio

    parsed_job_id = uuid.UUID(job_id)
    try:
        return asyncio.run(_clean_verified_sources(parsed_job_id))
    except Exception as exc:
        message = _safe_error(exc)
        asyncio.run(_set_ingestion_failure(parsed_job_id, message))
        return {"status": "failed", "job_id": job_id, "error": message}


async def _analyze_interview_turns(job_id: uuid.UUID) -> dict[str, Any]:
    import time

    from sqlalchemy import text, update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    settings = get_settings()
    provider: OpenAITranscriptCleanupProvider | GeminiTranscriptCleanupProvider
    if settings.extraction_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        provider = GeminiTranscriptCleanupProvider(
            settings.gemini_api_key,
            settings.extraction_model,
            settings.gemini_extraction_input_cost_per_million,
            settings.gemini_extraction_output_cost_per_million,
        )
    elif settings.extraction_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        provider = OpenAITranscriptCleanupProvider(
            settings.openai_api_key,
            settings.extraction_model,
            settings.openai_extraction_input_cost_per_million,
            settings.openai_extraction_output_cost_per_million,
        )
    else:
        raise ValueError("Interview-turn extraction requires EXTRACTION_PROVIDER=openai or gemini")
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                raise ValueError("The interview analysis job no longer exists")
            monthly_cost = float(
                await db.scalar(
                    text(
                        """
                        SELECT COALESCE(SUM(estimated_cost_usd), 0)
                        FROM provider_cost_records
                        WHERE provider IN ('openai', 'gemini')
                        AND created_at >= date_trunc('month', now())
                        """
                    )
                )
                or 0
            )
            if monthly_cost >= settings.max_monthly_ai_cost:
                raise ValueError("The configured monthly AI cost limit has been reached")
            source_id = uuid.UUID(str(job.payload["source_id"]))
            transcript_id = uuid.UUID(str(job.payload["transcript_id"]))
            source = await db.get(Source, source_id)
            if source is None:
                raise ValueError("The interview source no longer exists")
            founder_name = await db.scalar(
                text(
                    """
                    SELECT founder.name FROM founders founder
                    JOIN sources source ON source.founder_id=founder.id
                    WHERE source.id=:source_id
                    """
                ),
                {"source_id": source.id},
            )
            if not founder_name:
                raise ValueError("The founder record no longer exists")
            job.status = JobStatus.running
            job.started_at = datetime.now(UTC)
            job.progress = 10
            job.attempts += 1
            await db.commit()
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT id, start_seconds, end_seconds, text
                        FROM transcript_segments
                        WHERE transcript_id=:transcript_id
                        ORDER BY start_seconds, id
                        """
                    ),
                    {"transcript_id": transcript_id},
                )
            ).mappings().all()
            if not rows:
                raise ValueError("The interview has no caption segments")
            segments = [
                {
                    "segment_id": str(row["id"]),
                    "start_seconds": float(row["start_seconds"]),
                    "end_seconds": float(row["end_seconds"]),
                    "text": str(row["text"]),
                }
                for row in rows
            ]
            started = time.perf_counter()
            turns: list[dict[str, object]] = []
            usages: list[ProviderUsage] = []

            async def analyze_batch(batch: list[dict[str, object]]) -> None:
                try:
                    batch_turns, batch_usage = await provider.extract_interview_turns(
                        source.title,
                        str(founder_name),
                        batch,
                    )
                    turns.extend(batch_turns)
                    usages.append(batch_usage)
                except ValueError:
                    if len(batch) == 1:
                        item = batch[0]
                        turns.append(
                            {
                                "segment_ids": [str(item["segment_id"])],
                                "role": "uncertain",
                                "cleaned_text": str(item["text"]),
                                "confidence": 0.0,
                                "rationale": "Model output could not be validated for this segment.",
                                "start_seconds": cast(float, item["start_seconds"]),
                                "end_seconds": cast(float, item["end_seconds"]),
                            }
                        )
                        return
                    midpoint = len(batch) // 2
                    await analyze_batch(batch[:midpoint])
                    await analyze_batch(batch[midpoint:])

            batch_size = 120
            for offset in range(0, len(segments), batch_size):
                await analyze_batch(segments[offset : offset + batch_size])
                job.progress = min(
                    70,
                    10 + round(min(offset + batch_size, len(segments)) / len(segments) * 60),
                )
                await db.commit()
            if not usages:
                raise ValueError("The extraction provider did not produce any validated interview turns")
            first_usage = usages[0]
            usage = ProviderUsage(
                input_tokens=sum(item.input_tokens for item in usages),
                output_tokens=sum(item.output_tokens for item in usages),
                estimated_cost_usd=sum(item.estimated_cost_usd for item in usages),
                provider=first_usage.provider,
                model=first_usage.model,
                is_mock=first_usage.is_mock,
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            job.progress = 75
            await db.execute(
                update(InterviewTurnSuggestion)
                .where(
                    InterviewTurnSuggestion.source_id == source.id,
                    InterviewTurnSuggestion.status == "pending",
                )
                .values(status="superseded", reviewed_at=datetime.now(UTC))
            )
            auto_publish = settings.interview_turn_auto_publish_iyin
            auto_publish_min_confidence = settings.interview_turn_auto_publish_min_confidence
            founder_speaker_id: uuid.UUID | None = None
            version_id: uuid.UUID | None = None
            auto_approved_count = 0
            auto_rejected_count = 0
            if auto_publish:
                founder_speaker_id = await db.scalar(
                    text(
                        """
                        SELECT id FROM speakers
                        WHERE founder_id=:founder_id AND name=:name
                        LIMIT 1
                        """
                    ),
                    {"founder_id": source.founder_id, "name": founder_name},
                )
                if founder_speaker_id is None:
                    founder_speaker_id = uuid.uuid4()
                    await db.execute(
                        text(
                            """
                            INSERT INTO speakers (id, founder_id, name, role)
                            VALUES (:id, :founder_id, :name, 'founder')
                            """
                        ),
                        {
                            "id": founder_speaker_id,
                            "founder_id": source.founder_id,
                            "name": founder_name,
                        },
                    )
                approved_texts = [
                    str(turn["cleaned_text"])
                    for turn in turns
                    if turn["role"] == "iyin"
                    and float(cast(float, turn["confidence"])) >= auto_publish_min_confidence
                ]
                if approved_texts:
                    next_version = (
                        await db.scalar(
                            text(
                                """
                                SELECT COALESCE(MAX(version), 0) + 1
                                FROM source_versions
                                WHERE source_id=:source_id
                                """
                            ),
                            {"source_id": source.id},
                        )
                        or 1
                    )
                    version_id = uuid.uuid4()
                    joined_text = "\n\n".join(approved_texts)
                    await db.execute(
                        text(
                            """
                            INSERT INTO source_versions
                                (id, source_id, version, raw_artifact_id, cleaned_text, content_hash)
                            VALUES
                                (:id, :source_id, :version, :raw_artifact_id, :cleaned_text, :content_hash)
                            """
                        ),
                        {
                            "id": version_id,
                            "source_id": source.id,
                            "version": next_version,
                            "raw_artifact_id": source.raw_artifact_id,
                            "cleaned_text": joined_text,
                            "content_hash": content_hash(joined_text),
                        },
                    )
            for turn in turns:
                turn_role = str(turn["role"])
                confidence = float(cast(float, turn["confidence"]))
                chunk_id: uuid.UUID | None = None
                suggestion_status = "pending"
                reviewed_at = None
                if auto_publish:
                    reviewed_at = datetime.now(UTC)
                    if turn_role == "iyin" and confidence >= auto_publish_min_confidence:
                        flags = prompt_injection_flags(str(turn["cleaned_text"]))
                        chunk = Chunk(
                            source_id=source.id,
                            source_version_id=version_id,
                            speaker_id=founder_speaker_id,
                            text=str(turn["cleaned_text"]),
                            start_seconds=float(cast(float, turn["start_seconds"])),
                            end_seconds=float(cast(float, turn["end_seconds"])),
                            token_count=max(1, round(len(str(turn["cleaned_text"]).split()) * 1.3)),
                            speaker_verified=True,
                            answer_eligible=not bool(flags),
                            quality_flags=flags,
                            embedding=None,
                            embedding_model=None,
                            embedding_version="interview-turn-auto-approved-v1",
                        )
                        db.add(chunk)
                        await db.flush()
                        chunk_id = chunk.id
                        suggestion_status = "approved"
                        auto_approved_count += 1
                    else:
                        suggestion_status = "rejected"
                        auto_rejected_count += 1
                db.add(
                    InterviewTurnSuggestion(
                        source_id=source.id,
                        transcript_id=transcript_id,
                        job_id=job.id,
                        start_seconds=float(cast(float, turn["start_seconds"])),
                        end_seconds=float(cast(float, turn["end_seconds"])),
                        suggested_role=turn_role,
                        cleaned_text=str(turn["cleaned_text"]),
                        confidence=confidence,
                        rationale=str(turn["rationale"]),
                        segment_ids=[
                            str(item) for item in cast(list[str], turn["segment_ids"])
                        ],
                        status=suggestion_status,
                        chunk_id=chunk_id,
                        reviewed_at=reviewed_at,
                        model=usage.model,
                    )
                )
            await db.execute(
                text(
                    """
                    INSERT INTO api_usage_records
                        (provider, operation, tokens_in, tokens_out, latency_ms, correlation_id)
                    VALUES
                        (:provider, 'interview_flow_extraction', :tokens_in, :tokens_out,
                         :latency_ms, :correlation_id)
                    """
                ),
                {
                    "provider": usage.provider,
                    "tokens_in": usage.input_tokens,
                    "tokens_out": usage.output_tokens,
                    "latency_ms": latency_ms,
                    "correlation_id": job.correlation_id,
                },
            )
            await db.execute(
                text(
                    """
                    INSERT INTO provider_cost_records
                        (provider, operation, units, estimated_cost_usd, job_id)
                    VALUES
                        (:provider, 'interview_flow_extraction', :units, :cost, :job_id)
                    """
                ),
                {
                    "provider": usage.provider,
                    "units": usage.input_tokens + usage.output_tokens,
                    "cost": usage.estimated_cost_usd,
                    "job_id": job.id,
                },
            )
            job.status = JobStatus.succeeded
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            job.payload = {
                **job.payload,
                "turn_count": len(turns),
                "iyin_suggestion_count": sum(
                    1 for turn in turns if turn["role"] == "iyin"
                ),
                "estimated_extraction_cost_usd": round(usage.estimated_cost_usd, 6),
                "extraction_provider": usage.provider,
                "review_required": not auto_publish,
                "auto_publish_iyin": auto_publish,
                "auto_approved_chunk_count": auto_approved_count,
                "auto_rejected_turn_count": auto_rejected_count,
            }
            await db.commit()
            return {
                "status": "succeeded",
                "turn_count": len(turns),
                "estimated_extraction_cost_usd": round(usage.estimated_cost_usd, 6),
                "extraction_provider": usage.provider,
            }
    finally:
        await engine.dispose()


@celery_app.task(
    base=RetryingTask,
    name="afs.ai.analyze_interview_turns",
    rate_limit="10/m",
)
def analyze_interview_turns_task(job_id: str) -> dict[str, Any]:
    import asyncio

    parsed_job_id = uuid.UUID(job_id)
    try:
        return asyncio.run(_analyze_interview_turns(parsed_job_id))
    except Exception as exc:
        message = _safe_error(exc)
        asyncio.run(_set_ingestion_failure(parsed_job_id, message))
        return {"status": "failed", "job_id": job_id, "error": message}


@celery_app.task(name="afs.discovery.live")
def live_discovery() -> dict[str, str]:
    settings = get_settings()
    if not settings.live_crawling_enabled or not settings.zyte_api_key:
        return {"status": "disabled", "reason": "Live crawling and Zyte credentials are required"}
    return {"status": "configured", "reason": "Launch the Scrapy discovery spider with a reviewed query run"}


@celery_app.task(name="afs.operations.aggregate_costs")
def aggregate_costs(records: list[dict[str, float]]) -> dict[str, float]:
    ai = sum(record.get("ai_cost_usd", 0) for record in records)
    zyte = sum(record.get("zyte_cost_usd", 0) for record in records)
    return {"ai_cost_usd": round(ai, 6), "zyte_cost_usd": round(zyte, 6), "total_usd": round(ai + zyte, 6)}
