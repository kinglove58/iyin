import json
from pathlib import Path

import pytest
import scrapy
from scrapy.http import HtmlResponse, TextResponse
from services.crawler.afs_crawler.spiders.approved import ApprovedContentSpider
from services.crawler.afs_crawler.spiders.youtube import YouTubeDiscoverySpider


@pytest.mark.asyncio
async def test_youtube_discovery_keeps_key_out_of_url_and_emits_pending_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVE_CRAWLING_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_API_KEY", "safe-test-key")
    spider = YouTubeDiscoverySpider(query="fictional founder interview", max_results="1")
    requests = [request async for request in spider.start()]
    assert len(requests) == 1
    assert "safe-test-key" not in requests[0].url
    assert requests[0].headers["X-Goog-Api-Key"] == b"safe-test-key"

    payload = {
        "items": [
            {
                "id": {"videoId": "video123"},
                "snippet": {
                    "title": "Public interview",
                    "description": "A public research candidate",
                    "channelTitle": "Example channel",
                    "channelId": "channel123",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "thumbnails": {"default": {"url": "https://img.example/1.jpg"}},
                },
            }
        ]
    }
    response = TextResponse(
        requests[0].url,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        request=requests[0],
    )
    items = list(spider.parse(response, "fictional founder interview"))
    assert items[0]["approval_status"] == "pending"
    assert items[0]["platform_id"] == "video123"
    assert items[0]["source_api"] == "youtube_data_api_v3"


def test_approved_spider_uses_zyte_only_after_sparse_direct_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZYTE_API_KEY", "safe-test-key")
    manifest = tmp_path / "approved.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "id": "source-1",
                    "url": "https://example.com/research",
                    "approval_status": "approved",
                }
            ]
        ),
        encoding="utf-8",
    )
    spider = ApprovedContentSpider(str(manifest), zyte_mode="fallback")
    request = scrapy.Request(
        "https://example.com/research",
        meta={"source_id": "source-1", "approved": True, "fetch_strategy": "direct"},
    )
    response = HtmlResponse(
        request.url,
        body=b"<html><main><p>Too short.</p></main></html>",
        encoding="utf-8",
        request=request,
    )
    results = list(spider.parse(response))
    assert len(results) == 1
    fallback = results[0]
    assert isinstance(fallback, scrapy.Request)
    assert fallback.meta["fetch_strategy"] == "zyte_api"
    assert fallback.meta["zyte_api_automap"] == {"article": True, "articleBody": True}
