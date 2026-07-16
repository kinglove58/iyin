from typing import Any

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import CloseSpider
from scrapy.http import Request, Response


class CostAndEmergencyStop:
    def __init__(self, max_requests: int, max_zyte_requests: int, blocked_domains: set[str]) -> None:
        self.max_requests = max_requests
        self.max_zyte_requests = max_zyte_requests
        self.blocked_domains = blocked_domains
        self.requests = 0
        self.zyte_requests = 0
        self.crawler: Crawler | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "CostAndEmergencyStop":
        instance = cls(
            crawler.settings.getint("MAX_CRAWL_REQUESTS", 500),
            crawler.settings.getint("MAX_ZYTE_REQUESTS_PER_RUN", 0),
            {
                domain.strip().lower()
                for domain in crawler.settings.get("CRAWL_EMERGENCY_STOP_DOMAINS", "").split(",")
                if domain.strip()
            },
        )
        instance.crawler = crawler
        crawler.signals.connect(instance.request_scheduled, signal=signals.request_scheduled)
        crawler.signals.connect(instance.response_received, signal=signals.response_received)
        return instance

    def request_scheduled(self, request: Request, spider: Any) -> None:
        hostname = request.url.split("/")[2].split(":")[0].lower()
        if hostname in self.blocked_domains:
            raise CloseSpider("domain_emergency_stop")
        if (
            hostname == "www.googleapis.com"
            and "/youtube/v3/" in request.url
            and self.crawler
            and self.crawler.stats
        ):
            self.crawler.stats.inc_value("cost/youtube_api_requests")
        if "zyte_api" in request.meta or "zyte_api_automap" in request.meta:
            self.zyte_requests += 1
            if self.crawler and self.crawler.stats:
                self.crawler.stats.inc_value("cost/zyte_requests")
            if self.zyte_requests > self.max_zyte_requests:
                raise CloseSpider("per_run_zyte_request_limit")

    def response_received(self, response: Response, request: Request, spider: Any) -> None:
        self.requests += 1
        if self.requests >= self.max_requests:
            raise CloseSpider("per_run_request_limit")
