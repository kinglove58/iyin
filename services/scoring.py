from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CandidateSignals:
    direct_speaker: bool = False
    publisher_authority: float = 0.5
    long_form: bool = False
    transcript_available: bool = False
    publication_year: int | None = None
    topic_relevance: float = 0.5
    unique_content: float = 0.5
    original_available: bool = True
    duplicate_likelihood: float = 0.0
    extraction_feasibility: float = 0.5
    source_transparency: float = 0.5


DEFAULT_WEIGHTS = {
    "direct_speaker": 20.0,
    "publisher_authority": 12.0,
    "long_form": 8.0,
    "transcript_available": 10.0,
    "recency": 5.0,
    "topic_relevance": 12.0,
    "unique_content": 10.0,
    "original_available": 8.0,
    "duplicate_penalty": 8.0,
    "extraction_feasibility": 4.0,
    "source_transparency": 3.0,
}


def score_candidate(
    signals: CandidateSignals, weights: dict[str, float] | None = None
) -> tuple[float, dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
    current_year = date.today().year
    recency = (
        max(0.0, 1.0 - ((current_year - signals.publication_year) / 20))
        if signals.publication_year
        else 0.25
    )
    breakdown = {
        "direct_speaker": w["direct_speaker"] * float(signals.direct_speaker),
        "publisher_authority": w["publisher_authority"] * signals.publisher_authority,
        "long_form": w["long_form"] * float(signals.long_form),
        "transcript_available": w["transcript_available"] * float(signals.transcript_available),
        "recency": w["recency"] * recency,
        "topic_relevance": w["topic_relevance"] * signals.topic_relevance,
        "unique_content": w["unique_content"] * signals.unique_content,
        "original_available": w["original_available"] * float(signals.original_available),
        "duplicate_penalty": -w["duplicate_penalty"] * signals.duplicate_likelihood,
        "extraction_feasibility": w["extraction_feasibility"] * signals.extraction_feasibility,
        "source_transparency": w["source_transparency"] * signals.source_transparency,
    }
    return round(max(0.0, min(100.0, sum(breakdown.values()))), 2), {
        key: round(value, 2) for key, value in breakdown.items()
    }
