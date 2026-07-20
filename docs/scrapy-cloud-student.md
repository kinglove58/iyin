# Student Scrapy Cloud and hybrid crawling

## What the free unit does

The GitHub Student benefit supplies one Scrapy Cloud compute unit. It can run one
spider job at a time. It does not pay for Zyte API requests. The repository therefore
keeps cloud compute and paid extraction independent.

The recommended routing is:

1. Use YouTube Data API for official video discovery metadata.
2. Put every result into the pending candidate queue; discovery never approves it.
3. After human approval, try ordinary Scrapy HTTP first.
4. Use Zyte API fallback only for approved pages that fail or produce sparse text.
5. Preserve original bytes before cleaning, chunking, embedding, or answering.

## Run locally

Keep credentials only in the ignored `.env`. Enable live requests only for the run:

```env
YOUTUBE_API_KEY=replace-with-your-restricted-key
LIVE_CRAWLING_ENABLED=true
MAX_CRAWL_REQUESTS=100
MAX_ZYTE_REQUESTS_PER_RUN=0
```

Discover public YouTube candidates through the official API:

```bash
make discover-youtube
```

The Make target then imports the JSONL output idempotently into the protected admin
candidate queue. Every record remains `pending`; it does not create a source, chunk,
quotation, or answer-eligible record.

Run an approved manifest without paid Zyte requests:

```bash
docker compose run --rm --user root api sh -c \
  "cd services/crawler && scrapy crawl approved_content \
  -a approved_file=/app/fixtures/approved-sources.json -a zyte_mode=off"
```

If a Zyte API key is available, enable budgeted fallback:

```bash
make crawl-approved-hybrid
```

Before that paid run, deliberately change `MAX_ZYTE_REQUESTS_PER_RUN` from `0` to a
small nonzero value such as `5`. Zero is the fail-closed default.

The modes are `off`, `fallback`, and `always`. Keep `off` as the default. A missing
Zyte key in fallback mode simply leaves direct Scrapy active.

## Deploy to the student Scrapy Cloud unit

Create a Scrapy Cloud project in the Zyte dashboard and copy the numeric project ID
from its URL. The Scrapy Cloud API key is different from a Zyte API key. Do not put
either key in Git.

From this repository:

```bash
uvx --from shub shub login
cd services/crawler
uvx --from shub shub deploy YOUR_NUMERIC_PROJECT_ID
```

The first command asks for the Scrapy Cloud API key locally. The project already
contains `setup.py`, `requirements.txt`, and `scrapinghub.yml` for the cloud build.
The cloud configuration explicitly installs `requirements.txt`; this is required
for `scrapy-zyte-api` even when paid Zyte requests remain disabled.

For the safest student setup, run YouTube discovery locally so its key stays in
`.env`, and use Scrapy Cloud for direct approved crawling. To run YouTube discovery
in Scrapy Cloud instead, add restricted project settings named
`LIVE_CRAWLING_ENABLED=true` and `YOUTUBE_API_KEY=...`, then run the
`youtube_discovery` spider with one unit.

For approved cloud jobs, copy reviewed public records into
`afs_crawler/manifests/approved-sources.example.json`, redeploy, and run:

```text
spider: approved_content
approved_file: approved-sources.example.json
zyte_mode: off
units: 1
```

Only set `zyte_mode=fallback` after separately obtaining a Zyte API key and setting
`MAX_ZYTE_REQUESTS_PER_RUN` to a number you can afford. Scrapy Cloud items are stored
by the platform automatically, so the local JSONL feed is disabled in cloud jobs.

Export cloud discovery items as JSON Lines, place the file in `reports/`, and import
them locally with:

```bash
docker compose run --rm api python -m scripts.import_discovery \
  --file /app/reports/exported-cloud-items.jsonl
```

## Quota and privacy rules

- Start with one YouTube query and 5–10 results while testing.
- Never log, commit, paste, or place API keys in spider arguments.
- Restrict the Google key to YouTube Data API v3.
- Stop jobs that repeatedly fail or encounter robots, authentication, CAPTCHA, or
  rights restrictions.
- Treat API metadata as a discovery candidate, not evidence of a founder's views.
