import json
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import scrapy

from .discovery import BASE_QUERIES


class YouTubeDiscoverySpider(scrapy.Spider):
    """Discover public video metadata through the official YouTube Data API."""

    name = "youtube_discovery"
    allowed_domains = ["www.googleapis.com"]
    custom_settings = {"ROBOTSTXT_OBEY": False}

    def __init__(
        self,
        query: str | None = None,
        max_queries: str = "10",
        max_results: str = "10",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.queries = [query] if query else BASE_QUERIES
        self.max_queries = min(max(1, int(max_queries)), 20)
        self.max_results = min(max(1, int(max_results)), 50)
        self.seen_video_ids: set[str] = set()

    async def start(self) -> AsyncIterator[scrapy.Request]:
        if (
            os.getenv("LIVE_CRAWLING_ENABLED", "false").lower() != "true"
            and not self.settings.getbool("LIVE_CRAWLING_ENABLED")
        ):
            self.logger.warning("Live discovery disabled; no YouTube requests scheduled")
            return
        api_key = os.getenv("YOUTUBE_API_KEY") or self.settings.get("YOUTUBE_API_KEY", "")
        if not api_key:
            self.logger.error("YOUTUBE_API_KEY is required for YouTube discovery")
            return
        for query in self.queries[: self.max_queries]:
            params = {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": self.max_results,
                "safeSearch": "moderate",
                "relevanceLanguage": "en",
            }
            # A header prevents credentials from appearing in request URLs and logs.
            yield scrapy.Request(
                "https://www.googleapis.com/youtube/v3/search?" + urlencode(params),
                headers={"X-Goog-Api-Key": api_key},
                callback=self.parse,
                cb_kwargs={"discovery_query": query},
            )

    def parse(
        self, response: scrapy.http.Response, discovery_query: str
    ) -> Iterator[dict[str, object]]:
        payload = json.loads(response.text)
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not video_id or video_id in self.seen_video_ids:
                continue
            self.seen_video_ids.add(video_id)
            thumbnails = snippet.get("thumbnails", {})
            yield {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "publisher": snippet.get("channelTitle"),
                "platform": "youtube",
                "platform_id": video_id,
                "channel_id": snippet.get("channelId"),
                "published_at": snippet.get("publishedAt"),
                "thumbnail_url": thumbnails.get("high", thumbnails.get("default", {})).get("url"),
                "content_type": "video",
                "discovery_query": discovery_query,
                "discovered_at": datetime.now(UTC).isoformat(),
                "approval_status": "pending",
                "source_api": "youtube_data_api_v3",
            }
