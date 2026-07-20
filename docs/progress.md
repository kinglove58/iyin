# Progress

Updated: 2026-07-16

## Planning and policy

- [x] Read the master specification and applicable repository instructions.
- [x] Check current official Next.js, FastAPI, Scrapy, and Celery guidance.
- [x] Write the implementation plan.
- [x] Complete architecture, data, crawling, attribution, copyright, security,
  RAG, evaluation, admin, deployment, API, and troubleshooting documentation.

## Backend and data

- [x] Create the schema and migration, including pgvector.
- [x] Implement authentication, authorization, audit logs, and rate limiting.
- [x] Implement every required versioned API group with typed errors.
- [x] Implement provider abstraction, ingestion, retrieval, answers, and timelines.
- [x] Implement Celery jobs and job lifecycle controls.
- [x] Implement Scrapy discovery and approved-content modes.

## Frontend

- [x] Implement public research pages and cited ask flow.
- [x] Implement admin review, jobs, sources, chunks, analytics, evaluation, costs.
- [x] Verify accessibility, responsive behavior, and UI states.

## Operations and quality

- [x] Add Docker Compose, migrations, seed, fixtures, Make commands, and CI.
- [x] Pass Ruff, Mypy, ESLint, and TypeScript strict checks.
- [x] Pass Python, Vitest, Playwright, security, integration, and evaluation tests.
- [x] Build production assets and validate the local Compose stack.
- [x] Run fixture ingestion and fixture grounded-answer smoke tests.
- [x] Inspect diff and scan for secrets.
- [x] Publish the final implementation report with honest limitations.
- [x] Deploy all three crawler spiders to student Scrapy Cloud project 870427.
- [x] Complete zero-cost local and Scrapy Cloud crawler smoke tests.
- [x] Discover and import 104 unique YouTube videos as pending review candidates.
- [x] Add an accessible admin password visibility toggle and safely synchronize
  the persisted administrator credentials with the current local environment.
- [x] Add confirmed bulk approval for the pending candidate review queue while
  preserving per-candidate audit records.
- [x] Add caption-first background processing for approved YouTube sources with
  immutable raw storage, timestamped chunks, job progress, and paid transcription
  disabled by default.
- [x] Process 23 approved YouTube videos into 568 pending-review chunks, then
  activate the automatic cooldown when YouTube began blocking repeated requests.
- [x] Validate a controlled Zyte Proxy Mode transcript probe on one previously
  blocked video: three successful proxy requests returned 1,515 caption segments.
- [x] Add a production Zyte caption fallback with five-request per-video limits,
  a `$0.10` batch budget guard, per-job request and cost metrics, and admin cost
  visibility.
- [x] Process the remaining 81 approved YouTube sources through Zyte: 60
  succeeded, 21 were unavailable or had captions disabled, and the successful
  jobs used 180 client-observed proxy requests. Zyte Stats later showed an
  approximately `$0.29925` total batch charge.
- [x] Recalibrate Zyte planning from the dashboard-observed `$0.29925` batch cost;
  proxy request counts are retained as operational metrics but are no longer
  treated as billing units.
- [x] Add an audited, source-level speaker-review queue with explicit
  single-speaker verification, mixed-speaker hold, and not-founder decisions.
- [x] Complete and safety-audit the first speaker-review pass, leaving 16
  whole-video single-speaker sources and 92 answer-eligible chunks; default public
  answers to the Iyinoluwa Aboyeji collection so fixtures cannot cross scopes.
- [x] Replace mock Ask generation with OpenAI Responses structured output,
  conversation context, server-validated citations, timestamped YouTube links,
  provider usage/cost records, and OpenAI query embeddings.
- [x] Redesign Ask as a branded ChatGPT-style research conversation with starter
  questions, persistent composer, numbered inline citation links, source cards,
  confidence, and evidence limitations.
- [x] Add audited GPT transcript cleanup for verified single-speaker sources using
  new source versions and replacement chunks while retaining immutable captions.
- [x] Complete GPT cleanup and OpenAI embedding for all 16 verified sources:
  92 cleaned chunks are answer-eligible, their 92 raw-caption predecessors remain
  retained but disabled for answers, and completed provider records estimate
  `$0.227957` for cleanup plus `$0.000482` for evidence embeddings.
- [x] Split OpenAI generation and extraction price configuration, then select
  GPT-5.4 mini for grounded answers and GPT-5.4 nano for future transcript cleanup.
- [x] Add AI-assisted mixed-interview flow reconstruction from existing captions,
  with immutable suggestion records, timestamped video verification, explicit
  Iyin/interviewer/other/uncertain roles, and admin-gated RAG approval.
- [x] Run two GPT-5.4 nano interview pilots: an ambiguous 24-second clip produced
  no Iyin attribution for `$0.000619`; a clearer 2.6-minute interview produced 15
  pending turns, including 12 suggested Iyin turns, for `$0.003596`.
- [ ] Complete the mixed-interview bulk pass. OpenAI processed 20 of 47 sources
  before the account returned `insufficient_quota`; 415 timestamped Iyin passages
  are approved and answer-eligible, 433 interviewer/other/uncertain passages are
  rejected, and 105 already-classified Iyin passages remain pending embeddings.
  The recorded interview extraction cost is `$0.471054`, and processing can resume
  from the saved state after OpenAI API credits or billing capacity are restored.
- [x] Redesign the public landing experience around founder lessons, belief,
  purpose, and practical guidance for younger Africans; replace the technical
  collection dashboard with an optimized Iyinoluwa Aboyeji portrait, editorial
  color blocks, question-led journeys, human-readable library language, and
  responsive founder-first presentation.
- [x] Remove the standalone public source-library journey from navigation and
  redirect `/sources` to Ask; original videos and articles remain accessible
  through the citations attached directly to answers.
- [x] Replace the public methodology page with Elijah Obafemi's personal story,
  portrait, mission, contact details, and emotional motivation for building the
  project; refine the hero into a full-bleed portrait introduction inspired by
  Ventures Platform's centered editorial composition, while retaining the African
  Founder Studies palette and identity. Remove the résumé-like engineering and
  industry sections, remove Timeline from public navigation, and redirect it to
  the new About Elijah page.
- [x] Replace the temporary `AF` header badge and typed site name with the official
  responsive `afs_logo.svg` brand lockup on desktop and mobile.
- [x] Use `favicon.svg` as the browser icon and add the official brand lockup to the
  footer with an accessible, high-contrast treatment.
- [x] Add Gemini Developer API answer generation with structured output, server-side
  citation validation, token metrics, configuration warnings, and temporary
  PostgreSQL keyword retrieval that requires no OpenAI query-embedding credit.
