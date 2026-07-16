import pytest
from services.evaluation.dataset import PROMPTS, QUESTIONS
from services.evaluation.runner import run_evaluation


def test_versioned_dataset_has_required_breadth() -> None:
    assert len(QUESTIONS) >= 75
    assert set(PROMPTS) >= {"timeline", "prompt_injection", "speaker_attribution", "retrieval_edge"}


@pytest.mark.asyncio
async def test_grounding_evaluation_refuses_without_evidence() -> None:
    report = await run_evaluation()
    assert report["critical_grounding_regression"] is False
    assert report["no_evidence_refusal_rate"] == 1
