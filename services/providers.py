import hashlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .retrieval import Evidence


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    provider: str
    model: str
    is_mock: bool


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    confidence: str
    evidence_summary: str
    citations: list[dict[str, object]]
    contradictions: list[str]
    limitations: list[str]
    follow_up_questions: list[str]
    usage: ProviderUsage


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> tuple[list[list[float]], ProviderUsage]: ...


class AnswerProvider(ABC):
    @abstractmethod
    async def answer(self, question: str, evidence: list[Evidence]) -> GeneratedAnswer: ...


class StructuredExtractionProvider(ABC):
    @abstractmethod
    async def extract(self, text: str, schema_name: str) -> dict[str, object]: ...


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, artifact_uri: str) -> list[dict[str, object]]: ...


class RerankingProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, passages: list[str]) -> list[float]: ...


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], ProviderUsage]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha512(text.encode()).digest()
            values = [((digest[i % len(digest)] / 255) * 2) - 1 for i in range(self.dimensions)]
            norm = math.sqrt(sum(value * value for value in values)) or 1
            vectors.append([value / norm for value in values])
        tokens = sum(max(1, round(len(text.split()) * 1.3)) for text in texts)
        return vectors, ProviderUsage(tokens, 0, 0, "mock", "deterministic-v1", True)


class MockAnswerProvider(AnswerProvider):
    async def answer(self, question: str, evidence: list[Evidence]) -> GeneratedAnswer:
        if not evidence:
            return GeneratedAnswer(
                answer="I could not find sufficient approved evidence to answer this question.",
                confidence="low",
                evidence_summary="No eligible evidence was retrieved.",
                citations=[],
                contradictions=[],
                limitations=["The approved collection does not currently support this answer."],
                follow_up_questions=[],
                usage=ProviderUsage(len(question.split()), 12, 0, "mock", "grounded-template-v1", True),
            )
        citations: list[dict[str, object]] = [
            {
                "source_id": item.source_id,
                "title": item.title,
                "publisher": item.publisher,
                "publication_date": item.publication_date,
                "url": item.url,
                "start_seconds": item.start_seconds,
                "end_seconds": item.end_seconds,
                "supporting_excerpt": item.text[:240],
            }
            for item in evidence[:4]
        ]
        return GeneratedAnswer(
            answer=(
                "Based on the available public sources, the retrieved evidence addresses this "
                "question as summarized in the cited excerpts. This deterministic development "
                "answer is fixture/demo output, not a live model interpretation."
            ),
            confidence="medium" if len(evidence) > 1 else "low",
            evidence_summary=f"{len(evidence)} approved evidence segment(s) were retrieved.",
            citations=citations,
            contradictions=[],
            limitations=["Mock generation is active; review the cited source text directly."],
            follow_up_questions=[],
            usage=ProviderUsage(
                len(question.split()) + sum(len(item.text.split()) for item in evidence),
                34,
                0,
                "mock",
                "grounded-template-v1",
                True,
            ),
        )
