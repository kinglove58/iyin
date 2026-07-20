import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import ValidationError
from pypdf import PdfReader
from services.content import content_hash, prompt_injection_flags
from services.providers import (
    AnswerProvider,
    EmbeddingProvider,
    GeminiAnswerProvider,
    MockAnswerProvider,
    MockEmbeddingProvider,
    OpenAIAnswerProvider,
    OpenAIEmbeddingProvider,
    ProviderUsage,
)
from services.retrieval import Evidence, reciprocal_rank_fusion
from services.scoring import CandidateSignals, score_candidate
from services.storage import RawEvidenceStore
from services.urls import normalize_url
from sqlalchemy import desc, func, select, text
from starlette.concurrency import run_in_threadpool

from .auth import (
    AdminUser,
    AppSettings,
    DbSession,
    create_session,
    current_user,
    hash_session_token,
    require_csrf,
    verify_password,
)
from .errors import AppError
from .models import (
    AuditLog,
    BackgroundJob,
    CandidateStatus,
    Chunk,
    CorrectionRequest,
    Founder,
    InterviewTurnSuggestion,
    JobStatus,
    Session,
    Source,
    SourceCandidate,
    Topic,
    User,
)
from .observability import ANSWERS, CITATIONS, PROVIDER_COST, PROVIDER_LATENCY
from .schemas import (
    AnalyzeInterviewRequest,
    AskRequest,
    CandidateBulkReview,
    CandidateCreate,
    CandidateResponse,
    CandidateReview,
    CleanVerifiedSourcesRequest,
    CorrectionCreate,
    FileImportMetadata,
    FounderResponse,
    InterviewTurnReviewRequest,
    JobCreate,
    LoginRequest,
    ManualImportRequest,
    ProcessApprovedSourcesRequest,
    SearchResult,
    SourceResponse,
    SpeakerReviewBulkRequest,
    TopicResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1")


async def audit(
    db: DbSession,
    request: Request,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            correlation_id=request.state.correlation_id,
        )
    )


@router.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
async def ready(db: DbSession, settings: AppSettings) -> dict[str, object]:
    await db.execute(select(1))
    return {"status": "ready", "warnings": settings.configuration_warnings}


@router.post("/auth/login", tags=["auth"])
async def login(body: LoginRequest, response: Response, db: DbSession, settings: AppSettings) -> dict[str, object]:
    result = await db.execute(select(User).where(func.lower(User.email) == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "The email or password is incorrect")
    record, token = await create_session(db, user.id, settings)
    await db.commit()
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return {"user": UserResponse.model_validate(user), "csrf_token": record.csrf_token}


@router.get("/auth/me", tags=["auth"])
async def me(user: Annotated[User | None, Depends(current_user)]) -> dict[str, object]:
    if user is None:
        raise AppError(401, "authentication_required", "No active session")
    return {"user": UserResponse.model_validate(user)}


@router.post("/auth/logout", tags=["auth"], dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response, db: DbSession) -> dict[str, bool]:
    token = request.cookies.get("session_token")
    if token:
        record = await db.scalar(select(Session).where(Session.token_hash == hash_session_token(token)))
        if record:
            await db.delete(record)
            await db.commit()
    response.delete_cookie("session_token", path="/")
    return {"logged_out": True}


@router.get("/founders", tags=["founders"], response_model=list[FounderResponse])
async def founders(db: DbSession) -> list[Founder]:
    return list((await db.scalars(select(Founder).order_by(Founder.name))).all())


@router.get("/founders/{slug}", tags=["founders"], response_model=FounderResponse)
async def founder(slug: str, db: DbSession) -> Founder:
    item = await db.scalar(select(Founder).where(Founder.slug == slug))
    if item is None:
        raise AppError(404, "founder_not_found", "The requested founder was not found")
    return item


@router.get("/topics", tags=["topics"], response_model=list[TopicResponse])
async def topics(db: DbSession) -> list[Topic]:
    return list((await db.scalars(select(Topic).order_by(Topic.name))).all())


@router.get("/topics/{slug}", tags=["topics"])
async def topic_detail(slug: str, db: DbSession) -> dict[str, object]:
    item = await db.scalar(select(Topic).where(Topic.slug == slug))
    if item is None:
        raise AppError(404, "topic_not_found", "The requested topic was not found")
    return {"topic": TopicResponse.model_validate(item), "sources": [], "timeline": []}


@router.get("/candidates", tags=["candidates"], response_model=list[CandidateResponse])
async def candidates(
    _admin: AdminUser,
    db: DbSession,
    status: CandidateStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SourceCandidate]:
    statement = select(SourceCandidate).order_by(desc(SourceCandidate.score)).limit(limit)
    if status:
        statement = statement.where(SourceCandidate.status == status)
    return list((await db.scalars(statement)).all())


@router.post("/candidates", tags=["candidates"], response_model=CandidateResponse, status_code=201)
async def create_candidate(
    body: CandidateCreate, request: Request, admin: AdminUser, db: DbSession
) -> SourceCandidate:
    normalized = normalize_url(str(body.url), resolve_dns=True)
    if await db.scalar(select(SourceCandidate.id).where(SourceCandidate.normalized_url == normalized)):
        raise AppError(409, "duplicate_candidate", "This normalized URL is already in the review queue")
    score, breakdown = score_candidate(CandidateSignals())
    candidate = SourceCandidate(
        founder_id=body.founder_id,
        original_url=str(body.url),
        normalized_url=normalized,
        title=body.title,
        publisher=body.publisher,
        discovery_query=body.discovery_query,
        content_type=body.content_type,
        status=CandidateStatus.pending,
        score=score,
        score_breakdown=breakdown,
    )
    db.add(candidate)
    await db.flush()
    await audit(db, request, admin.id, "candidate.created", "source_candidate", candidate.id)
    await db.commit()
    await db.refresh(candidate)
    return candidate


async def approve_candidate(
    db: DbSession,
    candidate: SourceCandidate,
    admin: User,
    request: Request,
    note: str,
    source_tier: str,
    *,
    bulk: bool,
) -> uuid.UUID:
    candidate.status = CandidateStatus.approved
    candidate.reviewed_by = admin.id
    candidate.review_note = note
    source = Source(
        founder_id=candidate.founder_id,
        candidate_id=candidate.id,
        canonical_url=candidate.normalized_url,
        original_url=candidate.original_url,
        title=candidate.title,
        publisher=candidate.publisher,
        content_type=candidate.content_type,
        source_tier=source_tier,
        approval_status="approved",
        relevance_score=candidate.score,
    )
    db.add(source)
    await db.flush()
    await audit(
        db,
        request,
        admin.id,
        "candidate.approved",
        "source_candidate",
        candidate.id,
        {"note": note, "source_id": str(source.id), "bulk": bulk},
    )
    return source.id


@router.post(
    "/candidates/bulk-approve",
    tags=["candidates"],
    dependencies=[Depends(require_csrf)],
)
async def bulk_approve_candidates(
    body: CandidateBulkReview,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, object]:
    unique_ids = list(dict.fromkeys(body.candidate_ids))
    candidates_to_approve = list(
        (
            await db.scalars(
                select(SourceCandidate)
                .where(
                    SourceCandidate.id.in_(unique_ids),
                    SourceCandidate.status == CandidateStatus.pending,
                )
                .order_by(desc(SourceCandidate.score))
            )
        ).all()
    )
    if not candidates_to_approve:
        raise AppError(409, "no_pending_candidates", "None of the selected candidates are still pending")

    canonical_urls = [candidate.normalized_url for candidate in candidates_to_approve]
    existing_url = await db.scalar(
        select(Source.canonical_url).where(Source.canonical_url.in_(canonical_urls)).limit(1)
    )
    if existing_url:
        raise AppError(
            409,
            "source_already_exists",
            "A selected candidate already has a source record; refresh the queue and review it separately",
        )

    source_ids = [
        await approve_candidate(
            db,
            candidate,
            admin,
            request,
            body.note,
            body.source_tier,
            bulk=True,
        )
        for candidate in candidates_to_approve
    ]
    await db.commit()
    return {
        "approved_count": len(candidates_to_approve),
        "skipped_count": len(unique_ids) - len(candidates_to_approve),
        "source_ids": source_ids,
    }


@router.post(
    "/candidates/{candidate_id}/review",
    tags=["candidates"],
    dependencies=[Depends(require_csrf)],
)
async def review_candidate(
    candidate_id: uuid.UUID,
    body: CandidateReview,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, object]:
    candidate = await db.get(SourceCandidate, candidate_id)
    if candidate is None:
        raise AppError(404, "candidate_not_found", "The candidate was not found")
    if candidate.status != CandidateStatus.pending:
        raise AppError(409, "candidate_already_reviewed", "The candidate has already been reviewed")
    candidate.status = CandidateStatus(body.decision)
    candidate.reviewed_by = admin.id
    candidate.review_note = body.note
    source_id: uuid.UUID | None = None
    if body.decision == "approved":
        source_id = await approve_candidate(
            db,
            candidate,
            admin,
            request,
            body.note,
            body.source_tier,
            bulk=False,
        )
    else:
        await audit(
            db,
            request,
            admin.id,
            f"candidate.{body.decision}",
            "source_candidate",
            candidate.id,
            {"note": body.note, "source_id": None, "bulk": False},
        )
    await db.commit()
    return {"candidate_id": candidate.id, "decision": body.decision, "source_id": source_id}


@router.get("/sources", tags=["sources"], response_model=list[SourceResponse])
async def sources(
    db: DbSession,
    year: int | None = None,
    content_type: str | None = None,
    publisher: str | None = None,
    source_tier: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Source]:
    statement = select(Source).where(Source.approval_status == "approved").limit(limit)
    if year:
        statement = statement.where(func.extract("year", Source.publication_date) == year)
    if content_type:
        statement = statement.where(Source.content_type == content_type)
    if publisher:
        statement = statement.where(Source.publisher.ilike(f"%{publisher}%"))
    if source_tier:
        statement = statement.where(Source.source_tier == source_tier)
    return list((await db.scalars(statement.order_by(desc(Source.publication_date)))).all())


@router.get("/sources/{source_id}", tags=["sources"])
async def source_detail(source_id: uuid.UUID, db: DbSession) -> dict[str, object]:
    item = await db.get(Source, source_id)
    if item is None or item.approval_status != "approved":
        raise AppError(404, "source_not_found", "The source was not found")
    chunk_count = await db.scalar(select(func.count()).select_from(Chunk).where(Chunk.source_id == item.id))
    return {"source": SourceResponse.model_validate(item), "chunk_count": chunk_count or 0}


@router.post(
    "/sources/process-approved",
    tags=["sources", "ingestion-jobs"],
    dependencies=[Depends(require_csrf)],
    status_code=202,
)
async def process_approved_sources(
    body: ProcessApprovedSourcesRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, object]:
    if body.use_zyte_proxy and not settings.zyte_api_key:
        raise AppError(503, "zyte_not_configured", "Zyte API is not configured")
    if not body.use_zyte_proxy:
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
            raise AppError(
                429,
                "youtube_caption_cooldown",
                "YouTube is temporarily blocking caption requests. Use the approved Zyte fallback or wait.",
            )
    existing_jobs = list(
        (
            await db.scalars(
                select(BackgroundJob)
                .where(BackgroundJob.job_type == "youtube_caption_ingestion")
                .order_by(desc(BackgroundJob.created_at))
                .limit(500)
            )
        ).all()
    )
    latest_job_by_source: dict[str, BackgroundJob] = {}
    for existing_job in existing_jobs:
        existing_source_id = existing_job.payload.get("source_id")
        if existing_source_id:
            latest_job_by_source.setdefault(str(existing_source_id), existing_job)
    active_source_ids = {
        source_id
        for source_id, existing_job in latest_job_by_source.items()
        if existing_job.status in {JobStatus.queued, JobStatus.running}
    }
    sources_to_process = list(
        (
            await db.scalars(
                select(Source)
                .where(
                    Source.approval_status == "approved",
                    (
                        Source.canonical_url.ilike("%youtube.com/%")
                        | Source.canonical_url.ilike("%youtu.be/%")
                    ),
                    ~select(Chunk.id).where(Chunk.source_id == Source.id).exists(),
                )
                .order_by(desc(Source.relevance_score), Source.created_at)
                .limit(body.limit)
            )
        ).all()
    )
    sources_to_process = [
        source for source in sources_to_process if str(source.id) not in active_source_ids
    ]
    estimated_max_cost = (
        len(sources_to_process)
        * settings.zyte_caption_estimated_cost_per_video
        if body.use_zyte_proxy
        else 0
    )
    if estimated_max_cost > settings.max_zyte_caption_batch_cost:
        raise AppError(
            422,
            "zyte_batch_budget_exceeded",
            (
                f"The estimated maximum Zyte cost is ${estimated_max_cost:.4f}, "
                f"above the ${settings.max_zyte_caption_batch_cost:.2f} batch limit"
            ),
        )
    if not sources_to_process:
        return {
            "queued_count": 0,
            "message": "No unprocessed approved YouTube sources are available.",
            "paid_transcription_enabled": False,
        }

    jobs_to_dispatch: list[BackgroundJob] = []
    for source in sources_to_process:
        job = latest_job_by_source.get(str(source.id))
        if job is None:
            job = BackgroundJob(
                job_type="youtube_caption_ingestion",
                correlation_id=request.state.correlation_id,
                initiated_by=admin.id,
                payload={},
            )
            db.add(job)
        job.status = JobStatus.queued
        job.progress = 0
        job.correlation_id = request.state.correlation_id
        job.initiated_by = admin.id
        job.started_at = None
        job.finished_at = None
        job.error_details = None
        job.cancel_requested = False
        job.payload = {
            "source_id": str(source.id),
            "title": source.title,
            "url": source.canonical_url,
            "captions_only": True,
            "paid_transcription_enabled": False,
            "use_zyte_proxy": body.use_zyte_proxy,
            "max_zyte_requests": (
                settings.max_zyte_requests_per_video if body.use_zyte_proxy else 0
            ),
            "estimated_zyte_cost_usd_max": (
                settings.zyte_caption_estimated_cost_per_video
                if body.use_zyte_proxy
                else 0
            ),
        }
        jobs_to_dispatch.append(job)
    await db.flush()
    await audit(
        db,
        request,
        admin.id,
        "approved_sources.processing_queued",
        "background_job",
        None,
        {
            "job_count": len(jobs_to_dispatch),
            "captions_only": True,
            "paid_transcription_enabled": False,
            "use_zyte_proxy": body.use_zyte_proxy,
            "estimated_zyte_cost_usd_max": round(estimated_max_cost, 6),
        },
    )
    await db.commit()

    from apps.worker.worker.celery_app import celery_app

    for job in jobs_to_dispatch:
        celery_app.send_task("afs.ingestion.process_approved_source", args=[str(job.id)])
    return {
        "queued_count": len(jobs_to_dispatch),
        "job_ids": [job.id for job in jobs_to_dispatch],
        "message": "Public-caption processing was queued. Speaker review remains required.",
        "paid_transcription_enabled": False,
        "use_zyte_proxy": body.use_zyte_proxy,
        "estimated_zyte_cost_usd_max": round(estimated_max_cost, 6),
    }


@router.post(
    "/sources/clean-verified",
    tags=["sources"],
    dependencies=[Depends(require_csrf)],
)
async def clean_verified_sources(
    body: CleanVerifiedSourcesRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, object]:
    if settings.extraction_provider != "openai" or settings.embedding_provider != "openai":
        raise AppError(
            422,
            "openai_cleanup_not_enabled",
            "Select OpenAI for both extraction and embeddings before cleaning verified sources",
        )
    if not settings.openai_api_key:
        raise AppError(503, "provider_not_configured", "OPENAI_API_KEY is not configured")
    active = await db.scalar(
        select(BackgroundJob.id).where(
            BackgroundJob.job_type == "openai_transcript_cleanup",
            BackgroundJob.status.in_([JobStatus.queued, JobStatus.running]),
        )
    )
    if active:
        return {"queued": False, "job_id": active, "message": "Transcript cleanup is already active."}
    eligible_count = (
        await db.scalar(
            select(func.count(func.distinct(Chunk.source_id)))
            .join(Source, Source.id == Chunk.source_id)
            .where(
                Source.speaker_verified.is_(True),
                Chunk.answer_eligible.is_(True),
                Chunk.embedding_version == "youtube-caption-v1",
            )
        )
        or 0
    )
    if not eligible_count:
        return {"queued": False, "message": "No verified raw-caption sources need GPT cleanup."}
    job = BackgroundJob(
        job_type="openai_transcript_cleanup",
        status=JobStatus.queued,
        correlation_id=request.state.correlation_id,
        initiated_by=admin.id,
        payload={
            "limit": min(body.limit, eligible_count),
            "eligible_source_count": eligible_count,
            "generation_model": settings.extraction_model,
            "embedding_model": settings.embedding_model,
        },
    )
    db.add(job)
    await db.flush()
    await audit(
        db,
        request,
        admin.id,
        "verified_sources.cleanup_queued",
        "background_job",
        job.id,
        job.payload,
    )
    await db.commit()
    from apps.worker.worker.celery_app import celery_app

    celery_app.send_task("afs.ai.clean_verified_sources", args=[str(job.id)])
    return {
        "queued": True,
        "job_id": job.id,
        "source_count": min(body.limit, eligible_count),
        "message": "GPT cleanup and OpenAI embedding were queued for verified evidence.",
    }


@router.post("/sources/manual-import", tags=["sources"], dependencies=[Depends(require_csrf)])
async def manual_import(
    body: ManualImportRequest, request: Request, admin: AdminUser, db: DbSession
) -> dict[str, object]:
    url = normalize_url(str(body.original_source_url), resolve_dns=True)
    flags = prompt_injection_flags(body.content)
    job = BackgroundJob(
        job_type="manual_import",
        status=JobStatus.queued,
        correlation_id=request.state.correlation_id,
        initiated_by=admin.id,
        payload={
            "founder_id": str(body.founder_id),
            "url": url,
            "title": body.title,
            "publisher": body.publisher,
            "content_type": body.content_type,
            "attribution": body.attribution,
            "rights_note": body.rights_note,
            "content_sha256": hashlib.sha256(body.content.encode()).hexdigest(),
            "quality_flags": flags,
        },
    )
    db.add(job)
    await db.flush()
    await audit(db, request, admin.id, "manual_import.queued", "background_job", job.id)
    await db.commit()
    return {"job_id": job.id, "status": job.status, "quality_flags": flags}


ALLOWED_UPLOADS = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".pdf": {"application/pdf"},
    ".srt": {"application/x-subrip", "text/plain"},
    ".vtt": {"text/vtt", "text/plain"},
    ".json": {"application/json"},
    ".csv": {"text/csv", "application/csv", "text/plain"},
}


@router.post("/sources/import-file", tags=["sources"], dependencies=[Depends(require_csrf)], status_code=202)
async def import_file(
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings: AppSettings,
    metadata_json: Annotated[str, Form(alias="metadata")],
    upload: Annotated[UploadFile, File()],
) -> dict[str, object]:
    try:
        metadata = FileImportMetadata.model_validate_json(metadata_json)
    except ValidationError as exc:
        raise AppError(422, "invalid_import_metadata", "Import metadata is invalid", exc.errors()) from exc
    suffix = "." + (upload.filename or "").rsplit(".", 1)[-1].lower()
    allowed_mimes = ALLOWED_UPLOADS.get(suffix)
    if not allowed_mimes or upload.content_type not in allowed_mimes:
        raise AppError(415, "unsupported_file_type", "The extension and MIME type are not allowed")
    data = await upload.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise AppError(413, "file_too_large", "Manual import files may not exceed 10 MiB")
    if suffix == ".pdf":
        try:
            extracted_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        except Exception as exc:
            raise AppError(422, "invalid_pdf", "PDF text could not be safely extracted") from exc
    else:
        try:
            extracted_text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(422, "invalid_encoding", "Text imports must use UTF-8") from exc
    if len(extracted_text.strip()) < 20:
        raise AppError(422, "insufficient_content", "The imported file contains too little meaningful text")
    stored = await run_in_threadpool(
        RawEvidenceStore(settings).put_immutable,
        data,
        upload.content_type or "application/octet-stream",
        suffix=suffix,
    )
    job = BackgroundJob(
        job_type="file_import",
        status=JobStatus.queued,
        correlation_id=request.state.correlation_id,
        initiated_by=admin.id,
        payload={
            **metadata.model_dump(mode="json"),
            "url": normalize_url(str(metadata.original_source_url), resolve_dns=True),
            "filename": upload.filename,
            "media_type": upload.content_type,
            "raw_object_key": stored.object_key,
            "sha256": stored.sha256,
            "quality_flags": prompt_injection_flags(extracted_text),
            "malware_scan_status": "integration_required",
        },
    )
    db.add(job)
    await db.flush()
    await audit(db, request, admin.id, "file_import.queued", "background_job", job.id)
    await db.commit()
    return {
        "job_id": job.id,
        "raw_object_key": stored.object_key,
        "malware_scan_status": "integration_required",
        "note": "Configure malware scanning before automatic processing in production.",
    }


async def search_chunks(
    db: DbSession,
    question: str,
    limit: int = 8,
    founder_id: uuid.UUID | None = None,
    settings: AppSettings | None = None,
    usage_records: list[ProviderUsage] | None = None,
) -> list[SearchResult]:
    scope = (
        select(Chunk.id)
        .join(Source, Source.id == Chunk.source_id)
        .where(
            Chunk.answer_eligible.is_(True),
            Source.approval_status == "approved",
            Source.source_tier.in_(["A", "B"]),
        )
    )
    if founder_id is not None:
        scope = scope.where(Source.founder_id == founder_id)
    query_vector: list[list[float]] = []
    if settings and settings.embedding_provider == "keyword":
        # Temporary zero-cost retrieval mode. It avoids an external query-embedding
        # call while retaining the approved/source-scoped PostgreSQL text search.
        pass
    elif settings and settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise AppError(
                503,
                "provider_not_configured",
                "OpenAI embeddings are selected but no API key is configured",
            )
        embedding_provider: EmbeddingProvider = OpenAIEmbeddingProvider(
            settings.openai_api_key,
            settings.embedding_model,
            settings.embedding_dimensions,
            settings.openai_embedding_cost_per_million,
        )
        query_vector, embedding_usage = await embedding_provider.embed([question])
        if usage_records is not None:
            usage_records.append(embedding_usage)
    else:
        embedding_provider = MockEmbeddingProvider(
            settings.embedding_dimensions if settings else 1536
        )
        query_vector, embedding_usage = await embedding_provider.embed([question])
        if usage_records is not None:
            usage_records.append(embedding_usage)
    keyword_rank = list(
        (
            await db.scalars(
                scope.order_by(
                    func.ts_rank_cd(
                        func.to_tsvector("english", Chunk.text),
                        func.plainto_tsquery("english", question),
                    ).desc()
                ).limit(limit * 4)
            )
        ).all()
    )
    vector_rank: list[uuid.UUID] = []
    if query_vector:
        vector_rank = list(
            (
                await db.scalars(
                    scope.where(
                        Chunk.embedding.is_not(None),
                        Chunk.embedding_model
                        == (settings.embedding_model if settings else "deterministic-v1"),
                    )
                    .order_by(Chunk.embedding.cosine_distance(query_vector[0]))
                    .limit(limit * 4)
                )
            ).all()
        )
    fused = reciprocal_rank_fusion(
        [[str(item) for item in keyword_rank], [str(item) for item in vector_rank]]
    )
    rank_by_id = {uuid.UUID(item_id): score for item_id, score in fused}
    if not rank_by_id:
        return []
    rows = list(
        (
            await db.execute(
            select(Chunk, Source)
            .join(Source, Source.id == Chunk.source_id)
            .where(Chunk.id.in_(rank_by_id))
            )
        ).tuples().all()
    )
    rows.sort(key=lambda row: -rank_by_id[row[0].id])
    diversified: list[tuple[Chunk, Source]] = []
    work_counts: dict[uuid.UUID, int] = {}
    for row in rows:
        work_id = row[1].underlying_work_id
        if work_counts.get(work_id, 0) >= 2:
            continue
        diversified.append(row)
        work_counts[work_id] = work_counts.get(work_id, 0) + 1
        if len(diversified) >= limit:
            break
    return [
        SearchResult(
            chunk_id=chunk.id,
            source_id=source.id,
            title=source.title,
            publisher=source.publisher,
            publication_date=source.publication_date,
            url=source.canonical_url,
            text=chunk.text,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            combined_rank=round(rank_by_id[chunk.id], 6),
        )
        for chunk, source in diversified
    ]


@router.get("/search", tags=["search"], response_model=list[SearchResult])
async def search(
    q: Annotated[str, Query(min_length=3, max_length=1000)],
    db: DbSession,
    settings: AppSettings,
) -> list[SearchResult]:
    return await search_chunks(db, q, settings=settings)


def citation_url(url: str, start_seconds: float | None) -> str:
    if start_seconds is None or "youtu" not in url.lower():
        return url
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["t"] = str(max(0, round(start_seconds)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


async def record_provider_usage(
    db: DbSession,
    usage: ProviderUsage,
    operation: str,
    correlation_id: str,
    latency_ms: int,
) -> None:
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
            "latency_ms": latency_ms,
            "correlation_id": correlation_id,
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO provider_cost_records
                (provider, operation, units, estimated_cost_usd)
            VALUES
                (:provider, :operation, :units, :estimated_cost_usd)
            """
        ),
        {
            "provider": usage.provider,
            "operation": operation,
            "units": usage.input_tokens + usage.output_tokens,
            "estimated_cost_usd": usage.estimated_cost_usd,
        },
    )


@router.post("/ask", tags=["ask"])
async def ask(
    body: AskRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, object]:
    started = time.perf_counter()
    retrieval_usage: list[ProviderUsage] = []
    founder_id = body.founder_id or await db.scalar(
        select(Founder.id).where(Founder.slug == "iyinoluwa-aboyeji")
    )
    results = (
        await search_chunks(
            db,
            body.question,
            founder_id=founder_id,
            settings=settings,
            usage_records=retrieval_usage,
        )
        if founder_id is not None
        else []
    )
    evidence = [
        Evidence(
            chunk_id=str(item.chunk_id),
            source_id=str(item.source_id),
            title=item.title,
            publisher=item.publisher or "Unknown publisher",
            publication_date=item.publication_date.isoformat() if item.publication_date else None,
            url=citation_url(item.url, item.start_seconds),
            text=item.text,
            start_seconds=item.start_seconds,
            end_seconds=item.end_seconds,
        )
        for item in results
    ]
    history = [message.model_dump() for message in body.history]
    if settings.generation_provider == "openai":
        if not settings.openai_api_key:
            raise AppError(503, "provider_not_configured", "OpenAI generation is selected but no API key is configured")
        answer_provider: AnswerProvider = OpenAIAnswerProvider(
            settings.openai_api_key,
            settings.generation_model,
            settings.openai_generation_input_cost_per_million,
            settings.openai_generation_output_cost_per_million,
        )
    elif settings.generation_provider == "gemini":
        if not settings.gemini_api_key:
            raise AppError(
                503,
                "provider_not_configured",
                "Gemini generation is selected but no API key is configured",
            )
        answer_provider = GeminiAnswerProvider(
            settings.gemini_api_key,
            settings.generation_model,
            settings.gemini_generation_input_cost_per_million,
            settings.gemini_generation_output_cost_per_million,
        )
    else:
        answer_provider = MockAnswerProvider()
    try:
        generated = await answer_provider.answer(body.question, evidence, history)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise AppError(
                503,
                "provider_rate_limited",
                f"The {settings.generation_provider} answer provider is rate-limited right now. "
                "Please try again in a moment.",
            ) from exc
        raise AppError(
            502,
            "provider_error",
            f"The {settings.generation_provider} answer provider returned an error.",
        ) from exc
    except httpx.HTTPError as exc:
        raise AppError(
            502,
            "provider_unavailable",
            f"The {settings.generation_provider} answer provider is temporarily unavailable.",
        ) from exc
    latency_ms = round((time.perf_counter() - started) * 1000)
    await record_provider_usage(
        db,
        generated.usage,
        "answer_generation",
        request.state.correlation_id,
        latency_ms,
    )
    for usage in retrieval_usage:
        await record_provider_usage(
            db,
            usage,
            "query_embedding",
            request.state.correlation_id,
            latency_ms,
        )
    await db.execute(
        text(
            """
            INSERT INTO user_queries
                (founder_id, question, confidence, citation_count, refused, latency_ms)
            VALUES
                (:founder_id, :question, :confidence, :citation_count, :refused, :latency_ms)
            """
        ),
        {
            "founder_id": founder_id,
            "question": body.question,
            "confidence": generated.confidence,
            "citation_count": len(generated.citations),
            "refused": not evidence,
            "latency_ms": latency_ms,
        },
    )
    await db.commit()
    PROVIDER_LATENCY.labels(generated.usage.provider, "answer_generation").observe(
        latency_ms / 1000
    )
    PROVIDER_COST.labels(generated.usage.provider, "answer_generation").inc(
        generated.usage.estimated_cost_usd
    )
    for usage in retrieval_usage:
        PROVIDER_COST.labels(usage.provider, "query_embedding").inc(
            usage.estimated_cost_usd
        )
    CITATIONS.observe(len(generated.citations))
    ANSWERS.labels(generated.confidence, str(not evidence).lower()).inc()
    payload: dict[str, object] = {
        "answer": generated.answer,
        "confidence": generated.confidence,
        "evidence_summary": generated.evidence_summary,
        "citations": generated.citations,
        "contradictions": generated.contradictions,
        "limitations": generated.limitations,
        "follow_up_questions": generated.follow_up_questions,
        "provider": {
            "name": generated.usage.provider,
            "model": generated.usage.model,
            "is_mock": generated.usage.is_mock,
        },
    }
    if body.debug:
        payload["debug"] = {
            "filters": [
                "approved",
                "tier_a_or_b",
                "answer_eligible",
                "founder_scoped",
            ],
            "results": [item.model_dump(mode="json") for item in results],
            "reranker": settings.reranker_provider,
        }
    return payload


@router.get("/timelines", tags=["timelines"])
async def timelines(
    db: DbSession, founder_id: uuid.UUID | None = None, topic: str | None = None
) -> dict[str, object]:
    statement = select(Source).where(
        Source.approval_status == "approved", Source.publication_date.is_not(None)
    )
    if founder_id:
        statement = statement.where(Source.founder_id == founder_id)
    items = list((await db.scalars(statement.order_by(Source.publication_date))).all())
    return {
        "topic": topic,
        "events": [
            {"date": item.publication_date, "title": item.title, "source_id": item.id}
            for item in items
        ],
        "limitations": [] if items else ["No dated approved evidence is available."],
    }


@router.post("/corrections", tags=["corrections"], status_code=201)
async def create_correction(body: CorrectionCreate, db: DbSession) -> dict[str, object]:
    item = CorrectionRequest(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "status": item.status}


@router.get("/speaker-reviews", tags=["speaker-reviews"])
async def speaker_reviews(
    _admin: AdminUser,
    db: DbSession,
    status: Literal[
        "pending",
        "verified_single_speaker",
        "mixed_speakers",
        "rejected_not_founder",
        "all",
    ] = "pending",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict[str, object]]:
    records = (
        await db.execute(
            text(
                """
                SELECT
                    s.id AS source_id,
                    s.title,
                    s.publisher,
                    s.canonical_url,
                    s.speaker_verified,
                    f.name AS founder_name,
                    t.review_status,
                    COUNT(c.id)::int AS chunk_count,
                    COALESCE(MAX(c.end_seconds), 0) AS duration_seconds,
                    (
                        lower(s.title) LIKE '%iyin%'
                        OR lower(s.title) LIKE '%aboyeji%'
                    ) AS title_mentions_founder,
                    (
                        SELECT left(sample.text, 900)
                        FROM chunks sample
                        WHERE sample.source_id = s.id
                        ORDER BY sample.start_seconds NULLS FIRST, sample.created_at
                        LIMIT 1
                    ) AS excerpt
                FROM sources s
                JOIN founders f ON f.id = s.founder_id
                JOIN transcripts t ON t.source_id = s.id
                JOIN chunks c ON c.source_id = s.id
                WHERE c.embedding_version = 'youtube-caption-v1'
                AND (:status = 'all' OR t.review_status = :status)
                GROUP BY s.id, f.name, t.review_status
                ORDER BY
                    (
                        lower(s.title) LIKE '%iyin%'
                        OR lower(s.title) LIKE '%aboyeji%'
                    ) DESC,
                    s.title
                LIMIT :limit
                """
            ),
            {"status": status, "limit": limit},
        )
    ).mappings()
    return [dict(record) for record in records]


@router.post(
    "/interview-turns/analyze",
    tags=["speaker-reviews"],
    dependencies=[Depends(require_csrf)],
)
async def analyze_interview_turns(
    body: AnalyzeInterviewRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, object]:
    if settings.extraction_provider == "openai" and not settings.openai_api_key:
        raise AppError(422, "extraction_not_enabled", "OpenAI extraction is not configured")
    if settings.extraction_provider == "gemini" and not settings.gemini_api_key:
        raise AppError(422, "extraction_not_enabled", "Gemini extraction is not configured")
    if settings.extraction_provider not in ("openai", "gemini"):
        raise AppError(
            422,
            "extraction_not_enabled",
            "Interview-turn extraction requires EXTRACTION_PROVIDER=openai or gemini",
        )
    source = await db.get(Source, body.source_id)
    if source is None:
        raise AppError(404, "source_not_found", "The interview source was not found")
    transcript = (
        await db.execute(
            text(
                """
                SELECT id, review_status FROM transcripts
                WHERE source_id=:source_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"source_id": source.id},
        )
    ).mappings().first()
    if transcript is None or transcript["review_status"] != "mixed_speakers":
        raise AppError(422, "not_mixed_interview", "Only mixed-speaker transcripts can use this workflow")
    active_job = await db.scalar(
        select(BackgroundJob.id).where(
            BackgroundJob.job_type == "interview_turn_analysis",
            BackgroundJob.status.in_([JobStatus.queued, JobStatus.running]),
            BackgroundJob.payload["source_id"].as_string() == str(source.id),
        )
    )
    if active_job:
        return {"queued": False, "job_id": active_job, "message": "This interview is already being analyzed."}
    job = BackgroundJob(
        job_type="interview_turn_analysis",
        status=JobStatus.queued,
        correlation_id=request.state.correlation_id,
        initiated_by=admin.id,
        payload={
            "source_id": str(source.id),
            "transcript_id": str(transcript["id"]),
            "title": source.title,
            "model": settings.extraction_model,
        },
    )
    db.add(job)
    await db.flush()
    await audit(
        db,
        request,
        admin.id,
        "interview_turn_analysis.queued",
        "source",
        source.id,
        {"job_id": str(job.id), "model": settings.extraction_model},
    )
    await db.commit()
    from apps.worker.worker.celery_app import celery_app

    celery_app.send_task("afs.ai.analyze_interview_turns", args=[str(job.id)])
    return {"queued": True, "job_id": job.id, "message": "Interview flow analysis was queued."}


@router.get("/interview-turns", tags=["speaker-reviews"])
async def interview_turns(
    _admin: AdminUser,
    db: DbSession,
    source_id: uuid.UUID | None = None,
    status: Literal["pending", "approved", "rejected", "all"] = "pending",
    limit: Annotated[int, Query(ge=1, le=5000)] = 200,
) -> list[dict[str, object]]:
    statement = (
        select(InterviewTurnSuggestion, Source)
        .join(Source, Source.id == InterviewTurnSuggestion.source_id)
        .order_by(
            InterviewTurnSuggestion.source_id,
            InterviewTurnSuggestion.start_seconds,
        )
        .limit(limit)
    )
    if source_id:
        statement = statement.where(InterviewTurnSuggestion.source_id == source_id)
    if status != "all":
        statement = statement.where(InterviewTurnSuggestion.status == status)
    rows = (await db.execute(statement)).tuples().all()
    return [
        {
            "id": suggestion.id,
            "source_id": suggestion.source_id,
            "title": source.title,
            "publisher": source.publisher,
            "canonical_url": citation_url(source.canonical_url, suggestion.start_seconds),
            "start_seconds": suggestion.start_seconds,
            "end_seconds": suggestion.end_seconds,
            "suggested_role": suggestion.suggested_role,
            "cleaned_text": suggestion.cleaned_text,
            "confidence": suggestion.confidence,
            "rationale": suggestion.rationale,
            "status": suggestion.status,
            "model": suggestion.model,
        }
        for suggestion, source in rows
    ]


@router.post(
    "/interview-turns/review",
    tags=["speaker-reviews"],
    dependencies=[Depends(require_csrf)],
)
async def review_interview_turns(
    body: InterviewTurnReviewRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, object]:
    suggestions = list(
        (
            await db.scalars(
                select(InterviewTurnSuggestion).where(
                    InterviewTurnSuggestion.id.in_(body.suggestion_ids),
                    InterviewTurnSuggestion.status == "pending",
                )
            )
        ).all()
    )
    if len(suggestions) != len(set(body.suggestion_ids)):
        raise AppError(404, "suggestion_not_found", "One or more pending suggestions were not found")
    source_ids = {item.source_id for item in suggestions}
    if len(source_ids) != 1:
        raise AppError(422, "mixed_source_selection", "Review one interview source at a time")
    now = datetime.now(UTC)
    if body.decision == "reject":
        for suggestion in suggestions:
            suggestion.status = "rejected"
            suggestion.reviewed_by = admin.id
            suggestion.reviewed_at = now
        await audit(
            db,
            request,
            admin.id,
            "interview_turns.rejected",
            "source",
            next(iter(source_ids)),
            {"suggestion_ids": [str(item.id) for item in suggestions], "note": body.note},
        )
        await db.commit()
        return {"reviewed_count": len(suggestions), "approved_chunk_count": 0}
    if settings.embedding_provider != "openai" or not settings.openai_api_key:
        raise AppError(422, "openai_embeddings_not_enabled", "OpenAI embeddings are not configured")
    source_id = next(iter(source_ids))
    source = await db.get(Source, source_id)
    if source is None:
        raise AppError(404, "source_not_found", "The interview source was not found")
    founder = await db.get(Founder, source.founder_id)
    if founder is None:
        raise AppError(404, "founder_not_found", "The founder was not found")
    speaker_id = await db.scalar(
        text(
            "SELECT id FROM speakers WHERE founder_id=:founder_id AND name=:name LIMIT 1"
        ),
        {"founder_id": founder.id, "name": founder.name},
    )
    if speaker_id is None:
        speaker_id = uuid.uuid4()
        await db.execute(
            text("INSERT INTO speakers (id, founder_id, name, role) VALUES (:id, :founder_id, :name, 'founder')"),
            {"id": speaker_id, "founder_id": founder.id, "name": founder.name},
        )
    ordered = sorted(suggestions, key=lambda item: item.start_seconds)
    texts = [item.cleaned_text for item in ordered]
    embedding_provider = OpenAIEmbeddingProvider(
        settings.openai_api_key,
        settings.embedding_model,
        settings.embedding_dimensions,
        settings.openai_embedding_cost_per_million,
    )
    started = time.perf_counter()
    vectors, usage = await embedding_provider.embed(texts)
    latency_ms = round((time.perf_counter() - started) * 1000)
    next_version = (
        await db.scalar(
            text("SELECT COALESCE(MAX(version), 0) + 1 FROM source_versions WHERE source_id=:source_id"),
            {"source_id": source.id},
        )
        or 1
    )
    version_id = uuid.uuid4()
    joined_text = "\n\n".join(texts)
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
    for suggestion, vector in zip(ordered, vectors, strict=True):
        flags = prompt_injection_flags(suggestion.cleaned_text)
        chunk = Chunk(
            source_id=source.id,
            source_version_id=version_id,
            speaker_id=speaker_id,
            text=suggestion.cleaned_text,
            start_seconds=suggestion.start_seconds,
            end_seconds=suggestion.end_seconds,
            token_count=max(1, round(len(suggestion.cleaned_text.split()) * 1.3)),
            speaker_verified=True,
            answer_eligible=not bool(flags),
            quality_flags=flags,
            embedding=vector,
            embedding_model=usage.model,
            embedding_version="interview-turn-approved-v1",
        )
        db.add(chunk)
        await db.flush()
        suggestion.status = "approved"
        suggestion.chunk_id = chunk.id
        suggestion.reviewed_by = admin.id
        suggestion.reviewed_at = now
    await record_provider_usage(
        db,
        usage,
        "interview_turn_embedding",
        request.state.correlation_id,
        latency_ms,
    )
    await audit(
        db,
        request,
        admin.id,
        "interview_turns.approved_as_founder",
        "source",
        source.id,
        {
            "suggestion_ids": [str(item.id) for item in ordered],
            "chunk_count": len(ordered),
            "note": body.note,
        },
    )
    await db.commit()
    return {"reviewed_count": len(ordered), "approved_chunk_count": len(ordered)}


@router.post(
    "/speaker-reviews/bulk",
    tags=["speaker-reviews"],
    dependencies=[Depends(require_csrf)],
)
async def bulk_speaker_review(
    body: SpeakerReviewBulkRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, object]:
    source_ids = list(dict.fromkeys(body.source_ids))
    sources = list(
        (
            await db.scalars(
                select(Source).where(
                    Source.id.in_(source_ids),
                    Source.content_type == "transcript",
                )
            )
        ).all()
    )
    if len(sources) != len(source_ids):
        raise AppError(
            404,
            "speaker_review_source_not_found",
            "One or more transcript sources were not found",
        )

    verified = body.decision == "verified_single_speaker"
    speaker_id: uuid.UUID | None = None
    if verified:
        founder_ids = {source.founder_id for source in sources}
        if len(founder_ids) != 1:
            raise AppError(
                422,
                "mixed_founder_selection",
                "A bulk speaker decision can only cover one founder",
            )
        founder_id = next(iter(founder_ids))
        founder_name = await db.scalar(select(Founder.name).where(Founder.id == founder_id))
        if founder_name is None:
            raise AppError(404, "founder_not_found", "The founder was not found")
        speaker_id = await db.scalar(
            text(
                """
                SELECT id FROM speakers
                WHERE founder_id = :founder_id AND name = :name
                ORDER BY id
                LIMIT 1
                """
            ),
            {"founder_id": founder_id, "name": founder_name},
        )
        if speaker_id is None:
            speaker_id = uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO speakers (id, founder_id, name, role)
                    VALUES (:id, :founder_id, :name, 'founder')
                    """
                ),
                {
                    "id": speaker_id,
                    "founder_id": founder_id,
                    "name": founder_name,
                },
            )

    await db.execute(
        text(
            """
            UPDATE sources
            SET speaker_verified = :verified,
                rights_status = :rights_status,
                updated_at = now()
            WHERE id = ANY(:source_ids)
            """
        ),
        {
            "verified": verified,
            "rights_status": (
                "public_caption_speaker_verified"
                if verified
                else f"public_caption_{body.decision}"
            ),
            "source_ids": source_ids,
        },
    )
    updated_chunk_count = (
        await db.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.source_id.in_(source_ids))
        )
        or 0
    )
    await db.execute(
        text(
            """
            UPDATE chunks
            SET speaker_id = :speaker_id,
                speaker_verified = :verified,
                answer_eligible = (
                    :verified
                    AND COALESCE(jsonb_array_length(quality_flags), 0) = 0
                ),
                updated_at = now()
            WHERE source_id = ANY(:source_ids)
            """
        ),
        {
            "speaker_id": speaker_id,
            "verified": verified,
            "source_ids": source_ids,
        },
    )
    await db.execute(
        text(
            """
            UPDATE transcripts
            SET review_status = :decision
            WHERE source_id = ANY(:source_ids)
            """
        ),
        {"decision": body.decision, "source_ids": source_ids},
    )
    await db.execute(
        text(
            """
            DELETE FROM speaker_assignments
            WHERE segment_id IN (
                SELECT segment.id
                FROM transcript_segments segment
                JOIN transcripts transcript ON transcript.id = segment.transcript_id
                WHERE transcript.source_id = ANY(:source_ids)
            )
            """
        ),
        {"source_ids": source_ids},
    )
    await db.execute(
        text(
            """
            UPDATE transcript_segments
            SET speaker_id = :speaker_id,
                speaker_confidence = :confidence,
                review_status = :segment_status
            WHERE transcript_id IN (
                SELECT id FROM transcripts WHERE source_id = ANY(:source_ids)
            )
            """
        ),
        {
            "speaker_id": speaker_id,
            "confidence": 1.0 if verified else None,
            "segment_status": "verified" if verified else body.decision,
            "source_ids": source_ids,
        },
    )
    if verified and speaker_id is not None:
        await db.execute(
            text(
                """
                INSERT INTO speaker_assignments
                    (id, segment_id, speaker_id, assigned_by, confidence)
                SELECT
                    gen_random_uuid(),
                    segment.id,
                    :speaker_id,
                    :assigned_by,
                    1.0
                FROM transcript_segments segment
                JOIN transcripts transcript ON transcript.id = segment.transcript_id
                WHERE transcript.source_id = ANY(:source_ids)
                """
            ),
            {
                "speaker_id": speaker_id,
                "assigned_by": admin.id,
                "source_ids": source_ids,
            },
        )
    for source in sources:
        await audit(
            db,
            request,
            admin.id,
            "speaker_review.completed",
            "source",
            source.id,
            {
                "decision": body.decision,
                "note": body.note,
                "speaker_id": str(speaker_id) if speaker_id else None,
            },
        )
    await db.commit()
    return {
        "reviewed_count": len(sources),
        "decision": body.decision,
        "updated_chunk_count": updated_chunk_count,
        "answer_eligible": verified,
    }


@router.get("/chunks", tags=["chunks"])
async def chunks(_admin: AdminUser, db: DbSession, limit: int = 50) -> list[dict[str, object]]:
    items = list((await db.scalars(select(Chunk).limit(min(limit, 200)))).all())
    return [
        {"id": item.id, "source_id": item.source_id, "text": item.text, "answer_eligible": item.answer_eligible,
         "speaker_verified": item.speaker_verified, "quality_flags": item.quality_flags}
        for item in items
    ]


async def create_job_record(
    body: JobCreate, request: Request, admin: AdminUser, db: DbSession
) -> BackgroundJob:
    job = BackgroundJob(
        job_type=body.job_type,
        status=JobStatus.queued,
        correlation_id=request.state.correlation_id,
        initiated_by=admin.id,
        payload=body.payload,
    )
    db.add(job)
    await db.flush()
    await audit(db, request, admin.id, "job.queued", "background_job", job.id, body.payload)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/crawl-jobs", tags=["crawl-jobs"])
@router.get("/ingestion-jobs", tags=["ingestion-jobs"])
async def jobs(_admin: AdminUser, db: DbSession) -> list[dict[str, object]]:
    records = list(
        (
            await db.scalars(
                select(BackgroundJob).order_by(desc(BackgroundJob.created_at)).limit(200)
            )
        ).all()
    )
    return [{"id": j.id, "job_type": j.job_type, "status": j.status, "progress": j.progress,
             "attempts": j.attempts, "created_at": j.created_at, "finished_at": j.finished_at,
             "error_details": j.error_details, "payload": j.payload} for j in records]


@router.post("/crawl-jobs", tags=["crawl-jobs"], dependencies=[Depends(require_csrf)], status_code=202)
@router.post("/ingestion-jobs", tags=["ingestion-jobs"], dependencies=[Depends(require_csrf)], status_code=202)
async def queue_job(body: JobCreate, request: Request, admin: AdminUser, db: DbSession) -> dict[str, object]:
    job = await create_job_record(body, request, admin, db)
    return {"id": job.id, "status": job.status}


@router.post("/discovery", tags=["discovery"], dependencies=[Depends(require_csrf)], status_code=202)
async def discovery(request: Request, admin: AdminUser, db: DbSession, settings: AppSettings) -> dict[str, object]:
    if not settings.live_crawling_enabled:
        raise AppError(503, "live_crawling_disabled", "Live discovery is disabled; use fixture discovery")
    job = await create_job_record(JobCreate(job_type="serp_discovery"), request, admin, db)
    return {"id": job.id, "status": job.status}


@router.get("/evaluations", tags=["evaluations"])
async def evaluations(_admin: AdminUser) -> dict[str, object]:
    return {"dataset_version": "v1", "question_count": 75, "latest_run": None}


@router.get("/analytics", tags=["analytics"])
async def analytics(_admin: AdminUser, db: DbSession) -> dict[str, object]:
    source_count = await db.scalar(select(func.count()).select_from(Source))
    unique_count = await db.scalar(select(func.count(func.distinct(Source.underlying_work_id))))
    candidate_count = await db.scalar(select(func.count()).select_from(SourceCandidate))
    provider_costs = {
        str(record.provider): float(record.cost)
        for record in (
            await db.execute(
                text(
                    """
                    SELECT provider, COALESCE(SUM(estimated_cost_usd), 0) AS cost
                    FROM provider_cost_records
                    GROUP BY provider
                    """
                )
            )
        ).mappings()
    }
    return {
        "approved_source_records": source_count or 0,
        "unique_underlying_works": unique_count or 0,
        "candidate_records": candidate_count or 0,
        "estimated_ai_cost_usd": provider_costs.get("openai", 0),
        "estimated_zyte_cost_usd": provider_costs.get("zyte", 0),
        "zyte_cost_note": "Dashboard-observed costs are recorded as the billing source of truth.",
    }
