import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

import scrapy

BASE_QUERIES = [
    '"Iyinoluwa Aboyeji" interview', '"Iyin Aboyeji" interview',
    '"Iyinoluwa Aboyeji" podcast', '"Iyinoluwa Aboyeji" keynote',
    '"Iyinoluwa Aboyeji" fireside chat', '"Iyinoluwa Aboyeji" article',
    '"Iyinoluwa Aboyeji" essay', '"Iyinoluwa Aboyeji" speech',
    '"Iyinoluwa Aboyeji" transcript', '"Iyinoluwa Aboyeji" Future Africa',
    '"Iyinoluwa Aboyeji" Andela', '"Iyinoluwa Aboyeji" Flutterwave',
    '"Iyinoluwa Aboyeji" leadership', '"Iyinoluwa Aboyeji" fundraising',
    '"Iyinoluwa Aboyeji" talent', '"Iyinoluwa Aboyeji" venture capital',
    '"Iyinoluwa Aboyeji" Africa', '"Iyinoluwa Aboyeji" government',
    '"Iyinoluwa Aboyeji" faith', '"Iyinoluwa Aboyeji" entrepreneurship',
]


class DiscoverySpider(scrapy.Spider):
    name = "discovery"
    allowed_domains = ["google.com"]

    async def start(self) -> AsyncIterator[scrapy.Request]:
        if (
            os.getenv("LIVE_CRAWLING_ENABLED", "false").lower() != "true"
            and not self.settings.getbool("LIVE_CRAWLING_ENABLED")
        ):
            self.logger.warning("Live discovery disabled; no requests scheduled")
            return
        if not (os.getenv("ZYTE_API_KEY") or self.settings.get("ZYTE_API_KEY")):
            self.logger.error("ZYTE_API_KEY is required for Zyte SERP discovery")
            return
        for query in BASE_QUERIES:
            yield scrapy.Request(
                "https://www.google.com/search?q=" + quote_plus(query),
                meta={"zyte_api": {"serp": True}, "query": query},
                callback=self.parse,
            )

    def parse(self, response: scrapy.http.Response) -> Any:
        raw = getattr(response, "raw_api_response", {})
        for result in raw.get("serp", {}).get("organicResults", []):
            yield {
                "url": result.get("url"), "title": result.get("title"),
                "description": result.get("description"), "discovery_query": response.meta["query"],
                "discovered_at": datetime.now(UTC).isoformat(), "approval_status": "pending",
            }
