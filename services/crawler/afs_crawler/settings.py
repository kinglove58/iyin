import os

BOT_NAME = "afs_crawler"
SPIDER_MODULES = ["afs_crawler.spiders"]
NEWSPIDER_MODULE = "afs_crawler.spiders"

USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "AfricanFounderStudiesResearchBot/0.1 (+http://localhost:3000/methodology)",
)
ROBOTSTXT_OBEY = True
ROBOTSTXT_USER_AGENT = USER_AGENT
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2.0
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAXSIZE = 10 * 1024 * 1024
DOWNLOAD_WARNSIZE = 5 * 1024 * 1024
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 60.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5
RETRY_TIMES = 2
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
LOG_FORMATTER = "scrapy.logformatter.LogFormatter"
if os.getenv("SHUB_JOBKEY"):
    # Scrapy Cloud persists yielded items itself.
    FEEDS = {}
else:
    FEEDS = {
        os.getenv("CRAWLER_FEED_URI", "/app/reports/crawler-output.jsonl"): {
            "format": "jsonlines",
            "overwrite": True,
        }
    }
DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware": 1000,
}
REQUEST_FINGERPRINTER_CLASS = "scrapy_zyte_api.ScrapyZyteAPIRequestFingerprinter"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
LIVE_CRAWLING_ENABLED = os.getenv("LIVE_CRAWLING_ENABLED", "false").lower() == "true"
MAX_CRAWL_REQUESTS = int(os.getenv("MAX_CRAWL_REQUESTS", "500"))
MAX_ZYTE_REQUESTS_PER_RUN = int(os.getenv("MAX_ZYTE_REQUESTS_PER_RUN", "0"))
CRAWL_EMERGENCY_STOP_DOMAINS = os.getenv("CRAWL_EMERGENCY_STOP_DOMAINS", "")

EXTENSIONS = {"afs_crawler.extensions.CostAndEmergencyStop": 10}
