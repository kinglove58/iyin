import hashlib
import uuid
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import ValidationError
from pypdf import PdfReader
from services.content import prompt_injection_flags
from services.providers import MockAnswerProvider, MockEmbeddingProvider
from services.retrieval import Evidence, reciprocal_rank_fusion
from services.scoring import CandidateSignals, score_candidate
from services.storage import RawEvidenceStore
from services.urls import normalize_url
from sqlalchemy import desc, func, select
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
    JobStatus,
    Session,
    Source,
    SourceCandidate,
    Topic,
    User,
)
from .observability import ANSWERS
from .schemas import (
    AskRequest,
    CandidateCreate,
    CandidateResponse,
    CandidateReview,
    CorrectionCreate,
    FileImportMetadata,
    FounderResponse,
    JobCreate,
    LoginRequest,
    ManualImportRequest,
    SearchResult,
    SourceResponse,
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
    candidate.status = CandidateStatus(body.decision)
    candidate.reviewed_by = admin.id
    candidate.review_note = body.note
    source_id: uuid.UUID | None = None
    if body.decision == "approved":
        source = Source(
            founder_id=candidate.founder_id,
            candidate_id=candidate.id,
            canonical_url=candidate.normalized_url,
            original_url=candidate.original_url,
            title=candidate.title,
            publisher=candidate.publisher,
            content_type=candidate.content_type,
            source_tier=body.source_tier,
            approval_status="approved",
            relevance_score=candidate.score,
        )
        db.add(source)
        await db.flush()
        source_id = source.id
    await audit(
        db,
        request,
        admin.id,
        f"candidate.{body.decision}",
        "source_candidate",
        candidate.id,
        {"note": body.note, "source_id": str(source_id) if source_id else None},
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


async def search_chunks(db: DbSession, question: str, limit: int = 8) -> list[SearchResult]:
    scope = (
        select(Chunk.id)
        .join(Source, Source.id == Chunk.source_id)
        .where(
            Chunk.answer_eligible.is_(True),
            Source.approval_status == "approved",
            Source.source_tier.in_(["A", "B"]),
        )
    )
    query_vector, _usage = await MockEmbeddingProvider().embed([question])
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
    vector_rank = list(
        (
            await db.scalars(
                scope.where(Chunk.embedding.is_not(None))
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
async def search(q: Annotated[str, Query(min_length=3, max_length=1000)], db: DbSession) -> list[SearchResult]:
    return await search_chunks(db, q)


@router.post("/ask", tags=["ask"])
async def ask(body: AskRequest, db: DbSession, settings: AppSettings) -> dict[str, object]:
    results = await search_chunks(db, body.question)
    evidence = [
        Evidence(
            chunk_id=str(item.chunk_id),
            source_id=str(item.source_id),
            title=item.title,
            publisher=item.publisher or "Unknown publisher",
            publication_date=item.publication_date.isoformat() if item.publication_date else None,
            url=item.url,
            text=item.text,
            start_seconds=item.start_seconds,
            end_seconds=item.end_seconds,
        )
        for item in results
    ]
    generated = await MockAnswerProvider().answer(body.question, evidence)
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
            "filters": ["approved", "tier_a_or_b", "answer_eligible"],
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
    records = list((await db.scalars(select(BackgroundJob).order_by(desc(BackgroundJob.created_at)).limit(100))).all())
    return [{"id": j.id, "job_type": j.job_type, "status": j.status, "progress": j.progress,
             "attempts": j.attempts, "created_at": j.created_at, "error_details": j.error_details} for j in records]


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
    return {"approved_source_records": source_count or 0, "unique_underlying_works": unique_count or 0,
            "candidate_records": candidate_count or 0, "estimated_ai_cost_usd": 0, "estimated_zyte_cost_usd": 0}
