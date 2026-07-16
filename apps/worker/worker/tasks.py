# mypy: disable-error-code="untyped-decorator"

import hashlib
from typing import Any

from celery import Task
from services.content import content_hash, prompt_injection_flags, semantic_chunks
from services.providers import MockEmbeddingProvider
from services.scoring import CandidateSignals, score_candidate
from services.storage import RawEvidenceStore
from services.urls import normalize_url

from apps.api.afs.config import get_settings

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
