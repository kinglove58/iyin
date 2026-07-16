# Security threat model

## Assets and adversaries

Assets include administrator sessions, secrets, raw evidence, unpublished review
notes, source integrity, cost budgets, and answer grounding. Threats include account
takeover, SSRF through submitted URLs, malicious redirects, hostile uploads,
injection in crawled text, queue abuse, cost exhaustion, data exfiltration, and false
attribution.

## Controls

- Argon2 passwords, opaque hashed session tokens, HttpOnly/SameSite cookies, CSRF
  tokens, server-side role checks, rate limits, security headers, and audit events.
- URL scheme/credential validation plus DNS resolution blocking non-global,
  loopback, private, link-local, reserved, localhost, and metadata destinations.
  Redirect targets must be revalidated by retrieval clients.
- Response-size limits, MIME/file-size checks, immutable storage, content hashes,
  and a malware-scanning integration point before uploaded material is processed.
- Parameterized SQLAlchemy queries, strict request schemas, output encoding, secret
  redaction, conservative CORS, and explicit provider/cost configuration.
- Injection-pattern flags, XML-style evidence boundaries, approved-only filters,
  and a generator contract that source text cannot change instructions, call tools,
  remove citations, or request secrets.

## Residual risks

In-memory rate limits are per API replica and should be replaced with Redis-backed
limits at horizontal scale. Malware scanning requires an operator-selected scanner.
Human reviewers can still make attribution mistakes; evaluation and correction
workflows reduce but do not eliminate that risk.
