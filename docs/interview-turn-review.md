# AI-assisted interview-turn review

Mixed-speaker YouTube captions can be analyzed without downloading audio. This
workflow reconstructs likely question-and-answer turns from the existing immutable
caption segments.

## Configuration

Extraction runs through either OpenAI or the Gemini Developer API, selected by
`EXTRACTION_PROVIDER`:

```dotenv
EXTRACTION_PROVIDER=gemini
EXTRACTION_MODEL=gemini-2.5-flash-lite
GEMINI_API_KEY=your-private-key
GEMINI_EXTRACTION_INPUT_COST_PER_MILLION=0
GEMINI_EXTRACTION_OUTPUT_COST_PER_MILLION=0
```

Gemini extraction is useful specifically when OpenAI billing capacity is
exhausted, since it lets the mixed-interview bulk pass keep moving on a separate
account/credit. The monthly AI cost guard (`MAX_MONTHLY_AI_COST`) sums recorded
`openai` and `gemini` provider costs together, so it still caps total spend
regardless of which extraction provider is active.

`EXTRACTION_PROVIDER` also selects the model used by **Clean verified sources**
(GPT transcript cleanup, documented in
[OpenAI RAG answers and cleanup](openai-rag-and-cleanup.md)), which additionally
requires `EMBEDDING_PROVIDER=openai` for embedding-space consistency. Switch
`EXTRACTION_PROVIDER` back to `openai` before running that job.

Approving a suggested turn as Iyin always embeds the resulting chunk with
`OpenAIEmbeddingProvider` (`EMBEDDING_PROVIDER=openai` with a valid
`OPENAI_API_KEY`), independent of which provider produced the suggestion. This
keeps every answer-eligible vector in the same embedding space as the rest of the
collection. Gemini can unblock the extraction step while OpenAI is out of quota,
but final approval still needs working OpenAI embedding capacity.

## Safety boundary

GPT output is a suggestion, not speaker verification. Timestamped citations make
errors easier to detect, but a citation does not prove which person spoke. No
suggested turn enters public retrieval until an administrator approves it as Iyin.

Original transcript segments are never overwritten. Each analysis creates
`interview_turn_suggestions` records with:

- source, transcript, job, and original segment identifiers;
- start and end timestamps;
- suggested role: `iyin`, `interviewer`, `other`, or `uncertain`;
- cleaned text, confidence, rationale, model, and review status.

## Admin workflow

1. Open **Admin → Chunks**.
2. Under **AI-assisted interview review**, select a mixed-speaker source.
3. Select **Analyze interview**.
4. Wait for timestamped suggestions to appear.
5. Open **Verify video** for each passage being considered.
6. Select verified passages and choose **Approve as Iyin**, or reject incorrect
   suggestions.

Approval creates a new source version and new timestamped chunks with OpenAI
embeddings. Only those reviewed chunks become answer-eligible. The source itself
remains classified as mixed-speaker.

## Pilot results

On 2026-07-16:

- A 24-second ambiguous clip produced two conservative suggestions and no Iyin
  attribution, with estimated extraction cost `$0.000619`.
- The 2.6-minute “Why I Left Flutterwave - Iyin Aboyeji” clip produced 15 turns,
  including 12 suggested Iyin turns, with estimated extraction cost `$0.003596`.

All pilot suggestions remain pending human review.
