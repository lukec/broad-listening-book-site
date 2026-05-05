# Reader Listening Spec

Status: v0 shipped and deployed
Date: 2026-05-05
Repo: Broad Listening book site

## Summary

Add a reader-listening feature to the book website so readers can highlight a passage and contribute an anonymous, structured perspective tied to that passage.

This is not a public comment system, social network, issue tracker, or poll. It is a private listening record that helps the book team and DD2030 understand what the book is helping readers notice, question, challenge, or connect to.

The feature should embody the book's own broad-listening principles:

- collect open-text responses, not only predefined reactions
- preserve source context so responses can be interpreted responsibly
- discover themes and missing voices without claiming representativeness
- keep the reading experience calm and editorial
- export rich structured data for later analysis in broad-listening tools

## Product Goals

1. Let any reader respond to a selected passage with low friction.
2. Store anonymous, passage-linked feedback for private review and analysis.
3. Keep obscene, abusive, spammy, and unsafe content out of the dataset.
4. Support both English and Japanese pages.
5. Keep costs ultra low and predictable.
6. Preserve the existing GitHub Issues flow for concrete site/book problems.
7. Export the full rich dataset as JSONL and CSV for downstream tools.

## Non-Goals

- Public comments under chapters.
- Likes, votes, ranking, reactions, or popularity metrics.
- User accounts, profiles, handles, or email capture.
- Real-time dashboards.
- Automated DD2030 publishing in v0.
- Using broad-listening results as statistical public opinion.
- Replacing GitHub Issues for corrections, broken links, rendering bugs, or translation/site problems.

## Confirmed Decisions

- Availability: all readers, not only password-authenticated preview readers.
- Languages: English and Japanese.
- Identity: fully anonymous for v0.
- Storage: Cloudflare D1 is acceptable for v0.
- Export: full rich export is required so responses can be ingested into other analysis tools.
- Site/book problems: remain in GitHub Issues.
- Obscene language: block outright. This is an open-source community surface, not a free-for-all comment box.
- Moderation cost: avoid paid AI moderation in v0. Use deterministic server-side blocking, rate limits, spam rules, and optionally Cloudflare Turnstile.
- Turnstile: supported server-side, disabled by default for launch.
- Coarse location: store Cloudflare `client_country` when available, but never store raw IP addresses.
- Export: provide both a local Wrangler-backed export script and protected HTTP export endpoints.

## Current Implementation Status

As of 2026-05-05, the v0 reader-listening feature is implemented, deployed, and committed to `main`.

Production state:

- Site: `https://broadlisteningbook.com`
- Commit: `c7687b8 Add reader listening feedback flow`
- Last verified deployed Worker version: `00243ee4-1404-4b27-864a-eb43e275cb91`
- Production D1 database: `broad-listening-book-listening`
- Production D1 database id: `d314e0e4-a2fa-44dd-a71b-01420031f0a8`
- D1 migration `0001_listening_responses.sql` has been applied remotely.
- `LISTENING_EXPORT_TOKEN` is configured as a Cloudflare Worker secret.
- `LISTENING_REQUIRE_TURNSTILE=false` for launch.

Implemented behavior:

- English and Japanese chapter pages expose `Share passage` and `Contribute a perspective` when readers highlight text.
- The listening dialog submits anonymous, passage-linked responses to `/api/listening/submit`.
- Server-side validation, normalization, deterministic moderation, rate limiting, and the feature kill switch are implemented in the Worker.
- Accepted responses are stored in Cloudflare D1.
- Export is available through `scripts/export-listening.mjs` and protected HTTP endpoints.
- The web-only “Features of the Web Book” section is injected into the “How to Read This Book” pages during the site build, not into the manuscript repo.
- The injected section now appears last in that chapter and uses broad-listening language.

Not implemented yet:

- A repeatable DD2030 digest/report generator.
- Any automated DD2030 sharing workflow.
- Turnstile UI integration, because Turnstile is supported server-side but disabled for launch.
- A reviewed final pass on Japanese listening UI copy by a fluent editor.

## Reader Experience

The existing highlight/share behavior becomes a small passage action menu.

When the reader selects text inside a chapter:

- show `Share passage`
- show `Contribute a perspective`

Choosing `Share passage` keeps the existing native share behavior.

Choosing `Contribute a perspective` opens a compact dialog or bottom sheet. The selected passage remains visible at the top so the reader understands what they are responding to.

### English UI Copy

Selection action:

```text
Contribute a perspective
```

Dialog title:

```text
Add to the listening record
```

Prompt label:

```text
What should this passage help us hear?
```

Body copy:

```text
Share a perspective, concern, example, missing voice, or question. Your anonymous response will be stored with this passage for private review and analysis.
```

Lenses:

```text
Resonates
Challenge
Missing voice
Example
Question
```

Textarea placeholder:

```text
Add your perspective in your own words...
```

Moderation note:

```text
Obscene, abusive, spammy, or unsafe content is not accepted.
```

Submit:

```text
Contribute anonymously
```

Success:

```text
Thank you. Your anonymous response was added to the listening record.
```

Blocked:

```text
This response cannot be accepted because it appears to include obscene, abusive, spammy, or unsafe content.
```

### Japanese UI Copy

These strings are live in v0. They should still receive a fluent Japanese editorial review before the feature is promoted more broadly.

Selection action:

```text
視点を寄せる
```

Dialog title:

```text
広聴記録に加える
```

Prompt label:

```text
この箇所から、どんな声を聞くべきでしょうか？
```

Body copy:

```text
視点、懸念、事例、見落とされている声、問いを匿名で共有できます。投稿はこの箇所とともに保存され、非公開でレビューと分析に使われます。
```

Lenses:

```text
共感
異議
見落とされた声
事例
問い
```

Textarea placeholder:

```text
あなたの視点をあなたの言葉で書いてください...
```

Moderation note:

```text
わいせつ、攻撃的、スパム、安全でない内容は受け付けません。
```

Submit:

```text
匿名で送信
```

Success:

```text
ありがとうございます。匿名の回答が広聴記録に追加されました。
```

Blocked:

```text
この回答は、わいせつ、攻撃的、スパム、安全でない内容を含む可能性があるため受け付けられません。
```

## UX Requirements

- The feature must not interrupt normal reading.
- The highlight popover must remain small and positioned near the selected text.
- On mobile, the response form should behave as a bottom sheet rather than a cramped floating box.
- The selected passage should be truncated in the UI if long, but the stored record should include the selected text submitted by the client up to the server limit.
- The dialog must be keyboard accessible.
- Esc closes the dialog.
- Submitting must show clear success or blocked/error state.
- If JavaScript is unavailable, the page remains a readable static book. No fallback form is required in v0.

## Data Model

Store one row per submitted response.

Implemented D1 table:

```sql
CREATE TABLE listening_responses (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  lang TEXT NOT NULL,
  page_path TEXT NOT NULL,
  page_url TEXT NOT NULL,
  page_title TEXT NOT NULL,
  chapter_id TEXT,
  chapter_title TEXT,
  nearest_heading TEXT,
  selection_text TEXT NOT NULL,
  selection_text_sha256 TEXT NOT NULL,
  lens TEXT NOT NULL,
  response_text TEXT NOT NULL,
  response_text_sha256 TEXT NOT NULL,
  moderation_status TEXT NOT NULL,
  moderation_reason TEXT,
  user_agent_family TEXT,
  client_country TEXT,
  turnstile_verified INTEGER NOT NULL DEFAULT 0,
  export_consent TEXT NOT NULL DEFAULT 'private_analysis',
  schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_listening_created_at ON listening_responses(created_at);
CREATE INDEX idx_listening_lang ON listening_responses(lang);
CREATE INDEX idx_listening_page_path ON listening_responses(page_path);
CREATE INDEX idx_listening_lens ON listening_responses(lens);
CREATE INDEX idx_listening_moderation_status ON listening_responses(moderation_status);
```

Notes:

- Do not store raw IP addresses.
- If abuse prevention needs a repeat-submission key, store a daily salted hash of the IP and user-agent in a separate abuse table, not in the response export.
- `client_country` may come from Cloudflare request metadata and should be treated as rough operational context, not demographic data.
- `user_agent_family` should be coarse, such as `Safari`, `Chrome`, `Firefox`, `Edge`, `Other`, or `Unknown`.
- `export_consent` is fixed to `private_analysis` in v0 because there is no public quoting consent.

## Client Payload

The browser posts JSON to the Worker.

```json
{
  "schemaVersion": 1,
  "lang": "en",
  "pagePath": "/en/01_what_is_broad_listening.html",
  "pageUrl": "https://broadlisteningbook.com/en/01_what_is_broad_listening.html",
  "pageTitle": "Chapter 1: What Is Broad Listening?",
  "chapterId": "01_what_is_broad_listening",
  "chapterTitle": "Chapter 1: What Is Broad Listening?",
  "nearestHeading": "Broad Listening: A Technology for Hearing Many Voices",
  "selectionText": "Broad listening is a technology for hearing the voices of many people...",
  "lens": "missing_voice",
  "responseText": "I would like to hear more from people who are uncomfortable writing in public forms.",
  "turnstileToken": "optional-token"
}
```

Allowed lens values:

```text
resonates
challenge
missing_voice
example
question
```

## Worker API

### `POST /api/listening/submit`

Accepts one response.

Validation:

- Content-Type must be `application/json`.
- Request body max: 16 KB.
- `selectionText`: 12 to 1,000 characters after whitespace normalization.
- `responseText`: 3 to 2,000 characters after whitespace normalization.
- `lens`: must be one of the allowed lens values.
- `lang`: `en` or `ja`.
- `pagePath`: must be a site-local path under `/en/` or `/ja/`.
- `pageUrl`: must be same-origin.
- Reject HTML-heavy content, repeated URLs, obvious spam, and control characters.
- Apply server-side obscene/unsafe blocklist to `selectionText` and `responseText`.
- If Turnstile is enabled, verify token before insert.

Responses:

```json
{ "ok": true, "id": "lr_..." }
```

```json
{ "ok": false, "code": "blocked_content" }
```

```json
{ "ok": false, "code": "rate_limited" }
```

### `GET /api/listening/export.jsonl`

Protected endpoint for manual export.

Options:

- `?status=accepted`
- `?lang=en`
- `?since=2026-05-01`
- `?until=2026-05-31`

Returns newline-delimited JSON. Use `Content-Disposition` so the browser downloads a file.

### `GET /api/listening/export.csv`

Protected endpoint for spreadsheet workflows.

CSV should preserve the same core fields, with JSON-sensitive fields escaped safely.

### Protection Model For Export

Export endpoints must not be public.

Implemented v0:

- HTTP exports require `Authorization: Bearer <LISTENING_EXPORT_TOKEN>`.
- The export token is stored as a Cloudflare Worker secret.
- Local operators can also export through `npm run listening:export`, which uses Wrangler/D1 access instead of the HTTP token.
- Raw exports should go to `listening-exports/` or another ignored local path and must not be committed.

## Moderation

V0 moderation is deterministic and server-side.

Block outright:

- obscene terms
- direct abuse or slurs
- threats or encouragement of violence
- sexual content
- doxxing patterns
- spam links or repeated promotional text
- malware/phishing-looking URLs
- very high repetition or nonsense text

Do not block merely because a response is critical, angry, negative, or politically uncomfortable.

Implementation notes:

- Keep blocklists in Worker source or a small JSON module.
- Include English and Japanese terms.
- Normalize case, width, whitespace, and simple punctuation before matching.
- Return a generic blocked message. Do not echo the offending term.
- Log only aggregate moderation reason codes, not extra raw content.

Future option:

- Add AI moderation later if the response volume or false-positive/false-negative rate justifies the cost.

## Abuse Controls

Use layered low-cost controls:

- server-side validation
- rate limit by Cloudflare IP metadata
- optional Turnstile on the form
- reject repeated identical submissions by `response_text_sha256`
- cap submission body size
- disable endpoint quickly through Worker environment flag if abused

Suggested config:

```text
LISTENING_ENABLED=true
LISTENING_REQUIRE_TURNSTILE=false
LISTENING_EXPORT_TOKEN=<secret>
TURNSTILE_SECRET_KEY=<secret, only if enabled>
```

## Cost Notes

Pricing should be rechecked before material traffic changes because Cloudflare pricing can change.

As checked on 2026-05-03:

- D1 is available on Workers Free and Workers Paid.
- Workers Free includes D1 limits of 5 million rows read per day, 100,000 rows written per day, and 5 GB total storage.
- On the Free plan, exceeding daily D1 limits causes D1 queries to fail until reset rather than silently billing.
- Workers Paid includes larger D1 usage and then bills by rows read, rows written, and storage.
- D1 has no data transfer or egress charge.
- Cloudflare Turnstile has a Free plan with unlimited challenge/verification requests and up to 20 widgets.

References:

- <https://developers.cloudflare.com/d1/platform/pricing/>
- <https://developers.cloudflare.com/workers/platform/pricing/>
- <https://developers.cloudflare.com/turnstile/plans/>

Expected v0 cost:

- Near zero for normal book-site traffic and modest feedback volume.
- The main cost risk is abuse, not legitimate reader submissions.
- Avoiding AI moderation keeps marginal cost effectively limited to Worker and D1 usage.

## Export Format

JSONL should be the canonical full-fidelity export.

One record per line:

```json
{
  "id": "lr_01...",
  "created_at": "2026-05-03T20:15:30.000Z",
  "lang": "en",
  "page_path": "/en/01_what_is_broad_listening.html",
  "page_url": "https://broadlisteningbook.com/en/01_what_is_broad_listening.html",
  "page_title": "Chapter 1: What Is Broad Listening?",
  "chapter_id": "01_what_is_broad_listening",
  "chapter_title": "Chapter 1: What Is Broad Listening?",
  "nearest_heading": "Broad Listening: A Technology for Hearing Many Voices",
  "selection_text": "Broad listening is a technology for hearing the voices of many people...",
  "lens": "missing_voice",
  "response_text": "I would like to hear more from people who are uncomfortable writing in public forms.",
  "moderation_status": "accepted",
  "schema_version": 1
}
```

CSV should include the same fields where practical:

```text
id,created_at,lang,page_path,page_title,chapter_id,chapter_title,nearest_heading,selection_text,lens,response_text,moderation_status,moderation_reason,schema_version
```

Potential downstream ingestion modes:

- Kouchou AI / broad-listening tools: use `response_text` as the primary opinion text, with `selection_text`, `chapter_title`, `nearest_heading`, and `lens` as metadata.
- Editorial review: group by chapter and selected passage.
- DD2030 digest: summarize recurring themes, missing voices, challenges, and concrete examples.

## Manual DD2030 Sharing Workflow

Current v0 can be manual:

1. Export accepted JSONL or CSV.
2. Review and analyze the export locally or in another analysis tool.
3. Prepare a reviewed digest with selected anonymized examples.
4. Share the reviewed digest with DD2030.

A dedicated digest script is not implemented yet.

Suggested digest sections:

- Overview: date range, languages, response count.
- Top passages that generated responses.
- Themes by lens.
- Missing voices readers named.
- Challenges or risks readers raised.
- Concrete examples and references.
- Questions readers think DD2030 should ask next.
- Notes on limitations and participation bias.

Do not present counts as representative public opinion. Counts are operational signals only.

## Repo Boundaries

This repo should own:

- highlight response UI
- Worker submission API
- D1 schema and migrations
- export scripts
- listening-specific docs

This repo should not own:

- copied manuscript source
- raw public datasets checked into git
- secrets or D1 dumps
- private DD2030 analysis artifacts unless explicitly approved

## Verification

Local verification should include:

```sh
uv sync
uv run broad-book-build
npm run d1:migrate:local
npm run preview:worker
```

Rendering verification:

- Inspect an English chapter on desktop and mobile widths.
- Inspect a Japanese chapter on desktop and mobile widths.
- Highlight text and confirm both `Share passage` and `Contribute a perspective` appear.
- Submit an accepted response.
- Submit an obscene/unsafe test response and confirm it is blocked.
- Confirm the existing GitHub Issues feedback pages still work and are not conflated with listening responses.

Syntax and formatting verification:

```sh
git diff --check
node --check worker/src/index.js
node --check worker/src/listeningModeration.js
node --check scripts/export-listening.mjs
.venv/bin/python -m py_compile src/broad_listening_book_site/web_build.py
```

Post-deploy verification is documented in `README.md` and now includes listening-specific checks:

- live chapter pages include the selection action menu and listening dialog strings
- a valid production submission returns `{ "ok": true, "id": "lr_..." }`
- blocked content returns `blocked_content`
- unauthenticated HTTP export returns `401`
- `npm run listening:export -- --remote --format jsonl` can read accepted production rows
- smoke-test rows should be deleted after verification unless intentionally kept

## Remaining Open Questions

- Should Turnstile be enabled only after the first spam signal, or proactively before broader public sharing?
- Who should review the Japanese UI copy, and where should that review be captured?
- Should a digest script live in this repo if it creates private outputs, or should it only emit local ignored files?
- What should the first DD2030 digest format look like once real responses exist?

## Implementation Steps And Phases

### Phase 0: Spec And Design Lock - Complete

- Finalize this spec.
- Decide whether Turnstile is enabled at launch or delayed. Decision: delayed; server support exists, launch default is disabled.
- Decide whether `client_country` is stored. Decision: yes, when Cloudflare provides it, as rough operational context.
- Confirm Japanese copy enough for v0 launch. Follow-up fluent review remains open.

### Phase 1: Static UI - Complete

- Extend the existing selection popover in `src/broad_listening_book_site/web_build.py`.
- Add `Contribute a perspective` beside the existing native share action.
- Add accessible dialog or mobile bottom sheet.
- Add localized UI strings.
- Add client-side validation for length and required fields.
- Preserve the existing native share behavior.
- Inject “Features of the Web Book” into the generated web edition only, as the last section of “How to Read This Book”.

### Phase 2: Worker API And D1 Storage - Complete

- Add D1 binding to `wrangler.jsonc`.
- Add a D1 migration for `listening_responses`.
- Add `POST /api/listening/submit` to `worker/src/index.js`.
- Implement server-side validation, normalization, rate limiting, and deterministic moderation.
- Add environment flags for enabling/disabling the feature.
- Keep secrets out of git.

### Phase 3: Export - Complete

- Add a local export script for accepted responses.
- Emit JSONL as the canonical full-fidelity format.
- Emit CSV for spreadsheet review.
- Document the export command in `README.md`.
- Keep exported data ignored by git.
- Add protected HTTP export endpoints for JSONL and CSV.

### Phase 4: End-To-End QA - Complete

- Build the site locally.
- Run the Worker locally with D1.
- Test English and Japanese submissions.
- Test blocked obscene/unsafe submissions.
- Test export output.
- Inspect desktop and mobile rendering.
- Update `README.md` and `AGENTS.md` verification notes if needed.

### Phase 5: Manual Launch - Complete

- Create production D1 database.
- Apply D1 migration.
- Set Worker environment variables and secrets.
- Deploy Worker manually with Wrangler.
- Run the existing post-deploy checklist.
- Add listening-specific checks to the post-deploy report.
- Commit and push the feature to `origin/main`.

### Phase 6: DD2030 Digest - Not Started

- Export accepted responses for a date range.
- Generate a reviewed digest from JSONL.
- Share the digest manually with DD2030.
- Use real submission patterns to decide whether future work needs public summaries, AI-assisted synthesis, or additional moderation.
