# API

OpenAPI is served at `/api/openapi.json` and interactive documentation at
`/api/docs`. REST endpoints are under `/api/v1` for auth, founders, topics,
discovery, candidates, sources, crawl jobs, ingestion jobs, chunks, search, ask,
timelines, corrections, evaluations, analytics, and health.

Admin login sets an opaque HttpOnly cookie and returns a CSRF token. Send that token
as `X-CSRF-Token` with authenticated state-changing requests and include credentials.
Errors use `{error: {code, message, details, request_id}}`. Propagate
`X-Correlation-ID` for a workflow across HTTP and jobs. Liveness is
`/api/v1/health/live`, readiness is `/api/v1/health/ready`, and metrics are `/metrics`.
