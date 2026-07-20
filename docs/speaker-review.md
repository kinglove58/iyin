# Interview attribution

YouTube captions contain words and timestamps, but they do not reliably identify
who said each sentence. The project now handles interview attribution during the
AI interview-analysis job instead of requiring a separate admin review queue.

When an interview is analyzed, the extraction provider labels each turn as
`iyin`, `interviewer`, `other`, or `uncertain`. Confident `iyin` turns are written
directly as answer-eligible Ask chunks. Interviewer, other, uncertain, and
low-confidence turns are rejected automatically so they cannot be cited as
Iyinoluwa Aboyeji's words.

The old `/admin/chunks` page redirects to `/admin/jobs`. Use Jobs to monitor
caption ingestion, interview analysis, cleanup, failures, and provider cost.

For safety, original captions remain immutable. The automatic flow creates new
chunk records linked to timestamps and leaves rejected suggestions in the audit
trail for inspection.
