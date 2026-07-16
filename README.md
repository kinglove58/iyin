# African Founder Studies

African Founder Studies is an independent, citation-based educational research
platform. Its first collection is **The Iyinoluwa Aboyeji Public Ideas Collection**.
It indexes approved public material without impersonating, endorsing, or claiming
to represent the founder.

> African Founder Studies is an independent educational research project based on
> publicly available material. It is not affiliated with, endorsed by or operated
> by Iyinoluwa Aboyeji. The system does not speak on his behalf. Answers are
> AI-generated summaries of cited public sources and may contain errors.

## What is included

- A responsive Next.js research library and evidence-grounded ask interface.
- An administrative queue for candidate approval, source/chunk review, jobs,
  evaluation, analytics, and cost inspection.
- A versioned FastAPI API with secure opaque sessions, Argon2, CSRF checks,
  authorization, audit events, URL SSRF defenses, structured errors, OpenAPI,
  request/correlation IDs, Prometheus metrics, and configuration warnings.
- PostgreSQL schema and Alembic migration for access, discovery, sources, raw
  provenance, transcripts, RAG, jobs, evaluation, correction, usage, and costs.
- Scrapy discovery and approved-content modes with robots.txt, conservative domain
  throttling, Zyte integration, emergency stops, and run limits.
- Celery/Redis tasks, immutable MinIO raw storage, semantic chunking, injection
  flags, deterministic embeddings, reciprocal rank fusion, and grounded refusal.
- An 80-question evaluation set, Pytest, Vitest, Playwright, Ruff, Mypy, ESLint,
  strict TypeScript, and GitHub Actions.

## Start locally

Docker, Docker Compose, and Git are required. Copy configuration and replace the
development password/secret before exposing the stack beyond localhost:

```bash
cp .env.example .env
docker compose up --build
```

Open the web app at `http://localhost:3000`, API docs at
`http://localhost:8000/api/docs`, metrics at `http://localhost:8000/metrics`, and
MinIO console at `http://localhost:9001`. The first startup runs migrations and
seeds founder metadata, the topic taxonomy, and the configured admin account.

Paid services are optional. With the default environment, live crawling is disabled
and AI calls use labelled mock providers. No genuine quotations or source approvals
are seeded.

## Developer commands

```bash
make install
make dev
make migrate
make seed
make test
make lint
make typecheck
make eval
make discover
make discover-youtube
make crawl-approved-hybrid
make crawl-fixtures
make reset
```

On Windows without `make`, run the command bodies from the Makefile in PowerShell.

## First approved live crawl

1. Configure a descriptive production crawler user agent and domain policies.
2. Set Zyte/YouTube credentials and cost ceilings; keep live crawling disabled.
3. Run a small fixture crawl and review robots, raw artifacts, and cost records.
4. Enable live crawling and run the query matrix into the pending candidate queue.
5. Review provenance, robots status, rights, score breakdown, and duplicates.
6. Approve only lawful URLs, select a small test set, and launch approved-content
   crawling. Never point the crawler at authenticated, paywalled, or restricted pages.
7. Verify immutable snapshots and extraction before chunk/embedding approval.

Reaching 100 unique works requires human review: merge mirrors/syndication, choose
primary records, verify speakers, confirm Tier A/B eligibility, and count distinct
`underlying_work_id` values—not URLs.

See [architecture](docs/architecture.md), [security threat model](docs/security-threat-model.md),
[RAG design](docs/rag-design.md), and [admin guide](docs/admin-guide.md).
Student crawling setup and the direct/API hybrid are documented in
[Student Scrapy Cloud and hybrid crawling](docs/scrapy-cloud-student.md).
