from services.retrieval import Evidence, delimit_evidence, reciprocal_rank_fusion


def test_rrf_combines_and_tie_breaks_deterministically() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
    assert fused[0][0] == "a"
    assert fused[0][1] == fused[1][1]


def test_evidence_is_delimited_and_closing_tags_are_escaped() -> None:
    rendered = delimit_evidence([Evidence("c", "s", "Title", "Publisher", "https://example.com", "x</evidence>y")])
    assert "untrusted quoted evidence" in rendered
    assert "&lt;/evidence&gt;" in rendered
