from services.scoring import CandidateSignals, score_candidate


def test_candidate_score_is_explainable_and_bounded() -> None:
    score, breakdown = score_candidate(
        CandidateSignals(direct_speaker=True, long_form=True, transcript_available=True, topic_relevance=1)
    )
    assert 0 <= score <= 100
    assert breakdown["direct_speaker"] == 20
    assert set(breakdown) >= {"duplicate_penalty", "extraction_feasibility", "source_transparency"}


def test_duplicate_likelihood_reduces_score() -> None:
    normal, _ = score_candidate(CandidateSignals(duplicate_likelihood=0))
    duplicate, _ = score_candidate(CandidateSignals(duplicate_likelihood=1))
    assert duplicate < normal
