# Troubleshooting

- Readiness fails: confirm PostgreSQL health, `DATABASE_URL`, and migrations.
- Web shows empty shelves: run the seed, then approve/import genuine material; no
  fabricated source content is seeded.
- Live actions return 503: expected while `LIVE_CRAWLING_ENABLED=false` or required
  credentials are absent. Fixture tasks remain available.
- MinIO writes fail: confirm the init container created `S3_BUCKET` and credentials
  match the MinIO service.
- Admin mutation returns 403: sign in again and send the current CSRF token.
- Candidate URL is rejected: the SSRF guard blocks unresolved and non-global DNS;
  controlled Compose fixtures are run directly by the fixture crawler.
- pgvector dimension error: provider dimensions must match the migration; change via
  a coordinated migration and re-embedding job.
- Windows npm install appears stalled: avoid concurrent installs in the same app and
  wait for native package extraction to finish before running checks.
