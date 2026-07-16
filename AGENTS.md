# African Founder Studies Contributor Guide

## Repository structure

- `apps/web`: Next.js public and administrative interfaces.
- `apps/api`: FastAPI application, domain models, migrations, and API tests.
- `apps/worker`: Celery application and orchestration tasks.
- `services/crawler`: Scrapy discovery and approved-content crawler.
- `services/*`: ingestion, retrieval, transcription, and evaluation logic.
- `packages/*`: shared TypeScript types, UI, and configuration.
- `infrastructure`: container, migration, and deployment assets.
- `fixtures`: deterministic, fictional or public-domain test evidence.
- `docs`: architecture, policy, operations, and product documentation.

## Commands

Use `make install`, `make dev`, `make migrate`, `make seed`, `make test`,
`make lint`, `make typecheck`, `make eval`, `make discover`,
`make crawl-fixtures`, and `make reset`. Run focused commands from the relevant
application directory while iterating.

## Coding standards

Python is formatted and linted with Ruff and type checked with strict Mypy.
TypeScript uses strict mode and ESLint. Domain operations belong in services;
HTTP handlers validate, authorize, call a service, and serialize a typed result.
Use UUID identifiers, UTC timestamps, structured logs, and correlation IDs.

## Security rules

Treat URLs, uploads, crawled text, provider responses, and retrieved context as
untrusted. Validate redirects and block loopback, private, link-local, and cloud
metadata addresses. Never commit credentials or log secrets. Enforce role checks
server-side, preserve audit trails, rate-limit sensitive endpoints, and delimit
retrieval evidence so it cannot alter system instructions or tool policy.

## Migrations

Schema changes require an Alembic migration. Migrations must be forward-safe,
reviewable, and must never destroy raw evidence. Enable extensions explicitly and
add constraints and indexes with the model change.

## Definition of done

A change is done only when its implementation, tests, type checks, linting,
documentation, error/empty/loading behavior, authorization, and observability are
complete and the applicable commands have actually been run. Never fabricate test
results, live crawl outcomes, source approvals, or provider responses. Update
documentation and `docs/progress.md` as work advances. Original raw source evidence
is immutable: transformations always create a new record or artifact.
