import json
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import scrapy
from twisted.python.failure import Failure


class ApprovedContentSpider(scrapy.Spider):
    name = "approved_content"

    def __init__(
        self,
        approved_file: str,
        zyte_mode: str = "off",
        use_zyte: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        manifest_path = Path(approved_file)
        if not manifest_path.exists():
            manifest_path = Path(__file__).parents[1] / "manifests" / approved_file
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.records = [record for record in records if record.get("approval_status") == "approved"]
        # Keep the old argument compatible while making the three modes explicit.
        if use_zyte is not None:
            zyte_mode = "always" if use_zyte.lower() == "true" else "off"
        if zyte_mode not in {"off", "fallback", "always"}:
            raise ValueError("zyte_mode must be off, fallback, or always")
        self.zyte_mode = zyte_mode

    @property
    def has_zyte_key(self) -> bool:
        return bool(os.getenv("ZYTE_API_KEY") or self.settings.get("ZYTE_API_KEY"))

    async def start(self) -> AsyncIterator[scrapy.Request]:
        if self.zyte_mode == "always" and not self.has_zyte_key:
            raise ValueError("zyte_mode=always requires ZYTE_API_KEY")
        for record in self.records:
            meta: dict[str, object] = {
                "source_id": record["id"],
                "approved": True,
                "fetch_strategy": "direct",
            }
            if self.zyte_mode == "always":
                meta.update(self._zyte_meta())
            yield scrapy.Request(
                record["url"], callback=self.parse, errback=self.errback, meta=meta, dont_filter=False
            )

    @staticmethod
    def _zyte_meta() -> dict[str, object]:
        return {
            "fetch_strategy": "zyte_api",
            "zyte_api_automap": {"article": True, "articleBody": True},
        }

    def _fallback_request(self, request: scrapy.Request) -> scrapy.Request | None:
        if (
            self.zyte_mode != "fallback"
            or not self.has_zyte_key
            or request.meta.get("fetch_strategy") == "zyte_api"
        ):
            return None
        meta = dict(request.meta)
        meta.update(self._zyte_meta())
        return request.replace(meta=meta, dont_filter=True, errback=self.errback)

    def errback(self, failure: Failure) -> Iterator[scrapy.Request | dict[str, object]]:
        request = cast(scrapy.Request, failure.request)  # type: ignore[attr-defined]
        fallback = self._fallback_request(request)
        if fallback:
            self.logger.info("Direct fetch failed; using budgeted Zyte fallback for %s", request.url)
            yield fallback
            return
        yield {
            "source_id": request.meta["source_id"],
            "url": request.url,
            "status": 0,
            "robots_decision": "allowed_or_transport_failure",
            "crawl_timestamp": datetime.now(UTC).isoformat(),
            "strategy": request.meta.get("fetch_strategy", "direct"),
            "meaningful": False,
            "error": failure.getErrorMessage(),
        }

    def parse(self, response: scrapy.http.Response) -> Iterator[scrapy.Request | dict[str, object]]:
        article = response.raw_api_response.get("article") if hasattr(response, "raw_api_response") else None
        body = article.get("articleBody") if isinstance(article, dict) else None
        strategy = "zyte_article" if body else "static_html"
        text = body or "\n".join(response.css("main p::text, article p::text").getall()).strip()
        fallback = self._fallback_request(response.request) if response.request else None
        if len(text) < 200 and fallback:
            self.logger.info("Direct extraction was sparse; using budgeted Zyte fallback for %s", response.url)
            yield fallback
            return
        yield {
            "source_id": response.meta["source_id"],
            "url": response.url,
            "status": response.status,
            "robots_decision": "allowed",
            "crawl_timestamp": datetime.now(UTC).isoformat(),
            "strategy": strategy,
            "fetch_strategy": response.meta.get("fetch_strategy", "direct"),
            "meaningful": len(text) >= 200,
            "extracted_text": text,
            "raw_html": response.text,
        }
