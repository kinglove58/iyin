# Approved source processing

The admin **Jobs** page can queue every approved YouTube source that does not
already have chunks.

The default workflow is deliberately cost-safe:

1. Retrieve an English public caption track.
2. Preserve the original caption JSON as immutable raw evidence in object storage.
3. Create media, transcript, timestamped segment, and source-version records.
4. Create timestamped semantic chunks and deterministic local embeddings.
5. Leave every chunk `speaker_verified=false` and `answer_eligible=false`.

Public captions can be absent, disabled, age-restricted, region-restricted, or
temporarily blocked. Those cases become visible failed jobs. The system does not
download audio or call paid transcription as a fallback.

Direct caption requests activate a 30-minute cooldown after three recent YouTube
IP-block responses. Retrying after the cooldown reuses the existing failed or
deferred job records.

When an administrator explicitly selects **Process remaining with Zyte**, caption
requests use Zyte Proxy Mode instead. Each video is capped at five proxy requests,
each successful job records the request count and estimated cost, and the API
refuses to queue a batch whose maximum estimate exceeds `$0.50`. After the first
full batch billed approximately `$0.29925` for 81 attempted videos, future
estimates use an observed per-video planning value configured by
`ZYTE_CAPTION_ESTIMATED_COST_PER_VIDEO`. Zyte API Stats remains the billing source
of truth because proxy request counts do not equal Zyte billing units.

Successful caption processing does not establish who spoke each sentence. An
administrator must review speaker attribution before any new chunks become
answer-eligible.

## Controlled Zyte proxy probe

Run only after explicit approval for paid proxy traffic:

```bash
python -m scripts.probe_zyte_youtube_transcript \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --allow-one-video \
  --max-proxy-requests 5
```

The probe uses the official Zyte Proxy Mode endpoint and CA certificate, never
uses browser account cookies, and refuses to exceed the selected proxy-request
cap. Exact charges must be checked in Zyte API Stats because proxy responses do
not include billed price metadata.

## Admin workflow

1. Open `http://localhost:3010/admin/jobs` and sign in.
2. Select **Process remaining with Zyte**.
3. Confirm the displayed limits.
4. Watch Active, Succeeded, Failed, Deferred, and Recorded success cost. The page
   refreshes job state every four seconds. Zyte Stats includes requests made by
   failed jobs and is therefore the exact billing source.
5. Review failed jobs individually. Missing, disabled, private, regional, or
   non-English caption tracks are valid source-level failures and do not trigger
   paid audio transcription.
