import json

from scripts.import_discovery import parse_discovery_records


def test_discovery_import_accepts_only_pending_candidates() -> None:
    content = "\n".join(
        [
            json.dumps(
                {
                    "url": "https://youtube.com/watch?v=1",
                    "title": "Candidate",
                    "approval_status": "pending",
                }
            ),
            json.dumps(
                {
                    "url": "https://example.com/approved",
                    "title": "Approved",
                    "approval_status": "approved",
                }
            ),
            json.dumps({"title": "Missing URL", "approval_status": "pending"}),
        ]
    )
    records = parse_discovery_records(content)
    assert len(records) == 1
    assert records[0]["title"] == "Candidate"
