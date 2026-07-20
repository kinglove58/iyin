from apps.api.afs.main import app
from fastapi.testclient import TestClient


def test_live_health_and_openapi_groups() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    paths = client.get("/api/openapi.json").json()["paths"]
    for group in (
        "auth", "founders", "topics", "discovery", "candidates", "sources", "crawl-jobs",
        "ingestion-jobs", "chunks", "search", "ask", "timelines", "corrections", "evaluations",
        "analytics", "speaker-reviews", "interview-turns", "health",
    ):
        assert any(path.startswith(f"/api/v1/{group}") for path in paths), group
