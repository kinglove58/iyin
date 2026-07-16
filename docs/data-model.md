# Data model

UUIDs identify records and timestamps use UTC. The initial migration creates:

- Identity: users, roles, user roles, sessions, and immutable audit logs.
- Research: founders, aliases, topics, and founder/topic relationships.
- Discovery: queries, runs, candidates, reviews, and domain policies.
- Evidence: sources, versions, people, topics, relationships, raw artifacts, crawl
  attempts, and extraction attempts.
- Media: assets, transcripts, timestamped segments, speakers, and assignments.
- Retrieval: semantic chunks, topics, versioned embeddings, full-text documents,
  claims, and quotations.
- Operations: jobs/events, API/provider usage and costs, corrections, evaluation
  datasets/runs/results, user queries, and answer feedback.

Source records distinguish URLs from unique underlying works. Mirrors, excerpts,
transcripts, summaries, duplicates, and updated versions are relationships rather
than independent evidence. Vector dimensions are fixed by migration and must be
changed through a coordinated re-embedding migration.
