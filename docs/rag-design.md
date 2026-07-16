# RAG design

Cleaning preserves dates, questions, qualifications, examples, headings, speakers,
and timestamps while removing boilerplate. Semantic boundaries prefer complete
question/answer pairs, arguments, sections, stories, and transcript topics. Each
chunk retains neighboring context and exact offsets.

Retrieval filters approved Tier A/B, answer-eligible, verified material, then runs
PostgreSQL full-text and pgvector similarity, combines ranks with reciprocal rank
fusion, applies metadata filters, optionally reranks, and diversifies underlying
works. Debug mode exposes ranks and filters, not prompts or secrets.

The generator receives delimited untrusted evidence only. Important claims require
citations from retrieved records. Sparse evidence produces a refusal. Timeline
answers compare dated evidence cautiously and do not claim a change of mind without
strong support.
