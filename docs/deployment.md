# Deployment

Local Compose is a development topology, not a production security boundary. In
production use managed PostgreSQL with pgvector, Redis with authentication/TLS,
private S3 buckets and lifecycle controls, a secret manager, HTTPS termination,
multiple API/worker replicas, Redis-backed rate limiting, centralized OpenTelemetry
and metrics collection, backups, malware scanning, and egress policy for crawlers.

Run migrations as a one-shot release task before API rollout and seed only safe
reference metadata. Rotate the admin password and session secret, restrict CORS,
pin container digests, configure budgets, keep live crawling off until reviewed,
and verify readiness plus a fixture flow after deployment.
