# Speaker review

YouTube captions contain words and timestamps, but they do not reliably identify
who said each sentence. Caption ingestion therefore leaves all new evidence
ineligible for public answers until an administrator reviews attribution.

Open `http://localhost:3010/admin/chunks` to use the speaker-review queue. Each
record shows the video title, publisher, a caption excerpt, the number of chunks,
and a link to the original video. Selecting records enables three decisions:

- **Verify single speaker**: use only when every captioned statement can safely be
  attributed to Iyinoluwa Aboyeji. The source, transcript segments, and chunks are
  assigned to his speaker record. Chunks without quality flags become
  answer-eligible.
- **Hold as mixed speakers**: use for interviews, panels, podcasts, or any video
  where the captions combine multiple speakers. Its chunks remain ineligible
  until a future segment-level review or diarization workflow identifies turns.
- **Not Iyin**: use when the recording is commentary by someone else or otherwise
  does not contain attributable statements from the founder.

The title badge **Title names Iyin** is only a sorting aid. It is not speaker
verification. Every bulk action requires selected records, an explicit decision,
and a review note. Decisions update the source, transcript, transcript segments,
and chunks in one transaction and create one audit record per source.

After review, the public answer endpoint defaults to the Iyinoluwa Aboyeji
collection when a caller does not provide a founder identifier. This prevents
test fixtures or future founder collections from entering Iyin answers.

To reverse a decision, use the API decision `pending`; the interface can expose
this reset action later if routine reversals become necessary.
