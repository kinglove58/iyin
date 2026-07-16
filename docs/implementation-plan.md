# Implementation plan

## Objective

Build African Founder Studies as an independent, evidence-first research system.
The initial collection is The Iyinoluwa Aboyeji Public Ideas Collection, while the
domain model remains founder-agnostic. No content enters retrieval until an admin
approves it, and fixture statements are never attributed to a real person.

## Decisions

- Use a monorepo with a Next.js App Router frontend and a Python workspace shared
  by FastAPI, Celery, Scrapy, ingestion, retrieval, and evaluation services.
- Use SQLAlchemy 2 async models and Alembic over PostgreSQL/pgvector. Repositories
  keep API handlers small and permit deterministic SQLite-backed unit tests where
  PostgreSQL-only search behavior is replaced by an explicit mock.
- Use server-side opaque session cookies with Argon2 password hashing. Public
  accounts are supported by the role model but disabled by default.
- Store every raw response in S3/MinIO before parsing. Content-addressed object
  keys and immutable database records provide provenance.
- Implement mock AI providers as first-class adapters. Live adapters activate only
  with explicit provider configuration and credentials.
- Combine PostgreSQL full-text and pgvector ranks using reciprocal rank fusion,
  then diversify underlying works. Answer generation receives only delimited,
  approved, answer-eligible evidence.
- Keep live discovery and crawling off by default. Scrapy honors robots.txt,
  conservative per-domain throttling, allow/block policies, emergency stops, and
  cost ceilings.

## Delivery slices

1. Repository contracts, policies, environment schema, containers, and CI.
2. Database schema, migration, seed data, authentication, audit logs, and health.
3. Candidate discovery/review, source approval, job lifecycle, crawler, and raw
   evidence storage.
4. Cleaning, attribution, semantic chunking, embeddings, hybrid retrieval, cited
   answers, timelines, corrections, and evaluations.
5. Public library and admin workflows, with accessible responsive states.
6. Deterministic unit, integration, security, Vitest, and Playwright coverage.
7. Full local verification, production builds, Compose smoke checks, secret scan,
   and final progress/report updates.

## Validation

Run formatters, linters, strict type checks, unit/integration/security tests,
frontend tests, Playwright, evaluation checks, production builds, migrations,
seeding, container health checks, fixture ingestion, and one fixture grounded
answer. Live crawling is verified only when credentials and explicit approved test
URLs are available.
