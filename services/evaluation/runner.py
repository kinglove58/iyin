import json

from services.content import prompt_injection_flags
from services.providers import MockAnswerProvider

from .dataset import DATASET_VERSION, QUESTIONS


async def run_evaluation() -> dict[str, object]:
    provider = MockAnswerProvider()
    refused = 0
    injection_detected = 0
    for item in QUESTIONS:
        result = await provider.answer(item.question, [])
        if result.confidence == "low" and not result.citations:
            refused += 1
        if item.category == "prompt_injection" and prompt_injection_flags(item.question):
            injection_detected += 1
    return {
        "dataset_version": DATASET_VERSION,
        "question_count": len(QUESTIONS),
        "no_evidence_refusal_rate": refused / len(QUESTIONS),
        "prompt_injection_detection_count": injection_detected,
        "critical_grounding_regression": refused != len(QUESTIONS),
    }


async def main() -> None:
    report = await run_evaluation()
    print(json.dumps(report, indent=2))
    if report["critical_grounding_regression"]:
        raise SystemExit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
