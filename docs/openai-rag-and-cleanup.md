# OpenAI RAG answers and transcript cleanup

## Ask flow

The public Ask interface is conversational, but every request remains stateless:
the browser sends at most the last ten user/assistant messages with the current
question. The API retrieves evidence for the current question from approved Tier
A/B chunks in the selected founder collection.

Retrieval combines PostgreSQL full-text ranking and pgvector similarity using
reciprocal-rank fusion. OpenAI embeddings are compared only with chunks created by
the configured embedding model, preventing vectors from different models from
being mixed.

The answer provider receives:

- the current question and recent conversation context;
- server-selected evidence chunk IDs and text;
- source titles, publishers, dates, URLs, and timestamps.

The model is instructed to treat evidence as untrusted quoted material, answer
only from that evidence, avoid impersonation, and cite chunk IDs. The server
rejects any model-selected citation that is not in the retrieved evidence and
constructs the final source URLs itself. YouTube citations include the evidence
start time.

Provider token counts, estimated cost, latency, model, query confidence, and
citation count are recorded. Pricing inputs are configurable because provider
pricing can change.

## Transcript cleanup

Only sources already marked `verified_single_speaker` are eligible for automated
cleanup. Mixed-speaker and rejected sources remain excluded.

The cleanup job:

1. Reads the answer-eligible raw-caption chunks.
2. Asks the configured OpenAI extraction model to repair punctuation, casing,
   obvious recognition errors, and disfluencies without summarizing or adding
   facts.
3. Requires every input chunk ID exactly once. If a multi-chunk response is
   incomplete, it retries each chunk independently.
4. Creates a new `source_versions` row referencing the original immutable raw
   artifact.
5. Creates new timestamp-preserving chunks and OpenAI embeddings.
6. Disables the older caption chunks for answers only after the replacement
   version is safely written.

The original raw artifact, original source version, transcript segments, and old
chunks are retained. Cleanup is a derived evidence version, not a replacement for
the historical record.

## Configuration

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
GENERATION_PROVIDER=openai
GENERATION_MODEL=gpt-5.4-mini
EXTRACTION_PROVIDER=openai
EXTRACTION_MODEL=gpt-5.4-nano
OPENAI_GENERATION_INPUT_COST_PER_MILLION=0.75
OPENAI_GENERATION_OUTPUT_COST_PER_MILLION=4.50
OPENAI_EXTRACTION_INPUT_COST_PER_MILLION=0.20
OPENAI_EXTRACTION_OUTPUT_COST_PER_MILLION=1.25
OPENAI_EMBEDDING_COST_PER_MILLION=0.02
```

Keep `OPENAI_API_KEY` only in the uncommitted `.env` or a deployment secret
manager. Do not paste it into admin notes, logs, source records, or screenshots.

From **Admin → Jobs**, select **Clean verified sources** after speaker review.
Progress and estimated OpenAI cost appear on the same card.
