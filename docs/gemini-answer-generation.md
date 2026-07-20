# Gemini answer generation

Gemini can temporarily generate public Ask answers when OpenAI generation credit is
unavailable. The application continues to retrieve only approved, founder-scoped
evidence and validates every model-selected citation against that evidence.

## Local configuration

Create an API key in Google AI Studio and keep it only in the uncommitted `.env`:

```env
GEMINI_API_KEY=your-private-key
GENERATION_PROVIDER=gemini
GENERATION_MODEL=gemini-2.5-flash-lite
EMBEDDING_PROVIDER=keyword
```

Restart the API after changing `.env`:

```shell
docker compose up -d --build api web
```

`EMBEDDING_PROVIDER=keyword` is intentional for this temporary mode. Query vectors
must use the same embedding model as stored evidence vectors. Gemini query vectors
cannot be compared with the existing OpenAI vectors, and an exhausted OpenAI account
cannot generate a new query vector. Keyword mode therefore uses PostgreSQL full-text
ranking without an external embedding call. It is less semantic than hybrid vector
retrieval, but it remains deterministic, approved-source scoped, and cost-free.

The Gemini free tier has lower and account-specific rate limits. Inspect the active
project limits in Google AI Studio. Free-tier content may be used by Google to improve
its products, so send only the already-public evidence selected for answer generation.

