import json

import httpx
import pytest
from services.providers import (
    GeminiAnswerProvider,
    GeminiTranscriptCleanupProvider,
    MockAnswerProvider,
    MockEmbeddingProvider,
)
from services.retrieval import Evidence


@pytest.mark.asyncio
async def test_mock_embeddings_are_deterministic_and_labelled() -> None:
    provider = MockEmbeddingProvider(8)
    first, usage = await provider.embed(["fixture"])
    second, _ = await provider.embed(["fixture"])
    assert first == second
    assert len(first[0]) == 8
    assert usage.is_mock is True
    assert usage.estimated_cost_usd == 0


@pytest.mark.asyncio
async def test_answer_refuses_without_approved_evidence() -> None:
    answer = await MockAnswerProvider().answer("What is the private belief?", [])
    assert answer.confidence == "low"
    assert answer.citations == []
    assert "could not find sufficient approved evidence" in answer.answer


@pytest.mark.asyncio
async def test_gemini_answer_validates_citations_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "answer": "He emphasized patient building [chunk-1].",
                                            "confidence": "high",
                                            "evidence_summary": "One relevant passage was found.",
                                            "citation_chunk_ids": ["chunk-1", "invented"],
                                            "contradictions": [],
                                            "limitations": [],
                                            "follow_up_questions": ["What did he say about teams?"],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 30,
                    "thoughtsTokenCount": 5,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiAnswerProvider("test-key", client=client)
        answer = await provider.answer(
            "What did he emphasize?",
            [
                Evidence(
                    chunk_id="chunk-1",
                    source_id="source-1",
                    title="Public interview",
                    publisher="Example",
                    url="https://example.com/interview",
                    text="Patient company building matters.",
                )
            ],
        )

    assert answer.answer == "He emphasized patient building [1]."
    assert len(answer.citations) == 1
    assert answer.citations[0]["source_id"] == "source-1"
    assert answer.usage.provider == "gemini"
    assert answer.usage.input_tokens == 120
    assert answer.usage.output_tokens == 35


@pytest.mark.asyncio
async def test_gemini_extraction_extracts_interview_turns_in_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "turns": [
                                                {
                                                    "segment_ids": ["seg-1"],
                                                    "role": "interviewer",
                                                    "cleaned_text": "What did you learn?",
                                                    "confidence": 0.8,
                                                    "rationale": "Question phrasing.",
                                                },
                                                {
                                                    "segment_ids": ["seg-2"],
                                                    "role": "iyin",
                                                    "cleaned_text": "I learned patience.",
                                                    "confidence": 0.9,
                                                    "rationale": "Self-identifying context.",
                                                },
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {"promptTokenCount": 60, "candidatesTokenCount": 20},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiTranscriptCleanupProvider("test-key", "gemini-2.5-flash-lite", client=client)
        turns, usage = await provider.extract_interview_turns(
            "Founder interview",
            "Iyinoluwa Aboyeji",
            [
                {"segment_id": "seg-1", "start_seconds": 0.0, "end_seconds": 2.0, "text": "what did you learn"},
                {"segment_id": "seg-2", "start_seconds": 2.0, "end_seconds": 4.0, "text": "i learned patience"},
            ],
        )

    assert [turn["role"] for turn in turns] == ["interviewer", "iyin"]
    assert turns[1]["cleaned_text"] == "I learned patience."
    assert usage.provider == "gemini"
    assert usage.input_tokens == 60
    assert usage.output_tokens == 20


@pytest.mark.asyncio
async def test_gemini_extraction_rejects_reordered_segments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "turns": [
                                                {
                                                    "segment_ids": ["seg-2"],
                                                    "role": "iyin",
                                                    "cleaned_text": "Out of order.",
                                                    "confidence": 0.5,
                                                    "rationale": "n/a",
                                                }
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiTranscriptCleanupProvider("test-key", "gemini-2.5-flash-lite", client=client)
        with pytest.raises(ValueError, match="did not preserve every segment"):
            await provider.extract_interview_turns(
                "Founder interview",
                "Iyinoluwa Aboyeji",
                [
                    {"segment_id": "seg-1", "start_seconds": 0.0, "end_seconds": 2.0, "text": "a"},
                    {"segment_id": "seg-2", "start_seconds": 2.0, "end_seconds": 4.0, "text": "b"},
                ],
            )


@pytest.mark.asyncio
async def test_gemini_extraction_cleans_chunks_exactly_once() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "chunks": [
                                                {"chunk_id": "chunk-1", "cleaned_text": "Cleaned text one."},
                                                {"chunk_id": "chunk-2", "cleaned_text": "Cleaned text two."},
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 15},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiTranscriptCleanupProvider("test-key", "gemini-2.5-flash-lite", client=client)
        cleaned, usage = await provider.clean_chunks(
            "Founder interview",
            [
                {"chunk_id": "chunk-1", "text": "cleaned text one"},
                {"chunk_id": "chunk-2", "text": "cleaned text two"},
            ],
        )

    assert {item["chunk_id"] for item in cleaned} == {"chunk-1", "chunk-2"}
    assert usage.provider == "gemini"
    assert usage.model == "gemini-2.5-flash-lite"
