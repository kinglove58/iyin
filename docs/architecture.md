# Architecture

The browser talks to a versioned FastAPI service. FastAPI owns authorization,
metadata, review decisions, retrieval, and audit logging. Long-running work is
published to Celery through Redis. Scrapy performs discovery or approved-content
retrieval; only the latter receives administratively approved URLs. Original bytes
go to immutable S3/MinIO keys before transformation. PostgreSQL stores normalized
research records, full-text documents, pgvector embeddings, jobs, costs, and audit
history. Next.js renders both the public library and administrative workbench.

Mock providers are real adapters with explicit `is_mock` usage metadata. Provider
selection and model names come from environment variables. New founders share the
same tables and services, keyed by founder and collection metadata.

Trust boundaries are browser/API, administrator/API, crawler/public internet,
provider APIs, object storage, and worker queues. Crawled evidence never becomes an
instruction channel and never reaches RAG before approval and eligibility review.
