import pytest
from services.providers import MockAnswerProvider, MockEmbeddingProvider


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
