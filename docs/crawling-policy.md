# Crawling policy

Discovery produces candidates, never approved evidence. Approved-content crawling
accepts only records whose approval status is explicit. The crawler obeys robots.txt,
declares its user agent, limits concurrency to one request per domain, starts with a
two-second delay, enables conservative AutoThrottle, limits response size, records
timestamps/strategy/robots outcome, and supports request and domain emergency stops.

Do not access logged-in, private, paywalled, CAPTCHA-protected, or otherwise
restricted material. Do not scrape authenticated LinkedIn or X sessions. Prefer
official APIs for platform metadata. A lawful manual import with attribution and a
rights note is available when automation is inappropriate. Monthly and per-run
limits must be configured before live crawling.

The default approved-content strategy is direct Scrapy HTTP. `zyte_mode=fallback`
retries through Zyte API only after a transport failure or sparse extraction, and
only when a Zyte API key exists. `zyte_mode=always` is an explicit paid mode. The
per-run Zyte request ceiling is independent from the total request ceiling and is
recorded in Scrapy stats. YouTube discovery uses the official YouTube Data API;
its key is sent in an HTTP header so it is not exposed in request URLs or logs.
