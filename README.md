# broad-listening-book-site

Tooling repo for a pretty web version of the Broad Listening book.

This repo now owns the fancy multilingual HTML book build and the local live-reload dev server for the sibling manuscript repo at `../broad-listening-book`.

It does two main things:

1. builds the web edition from manuscript content in `../broad-listening-book`
2. serves its own generated `site/` directory, watches manuscript changes, and live-reloads browser tabs

## Requirements

- Python 3.10+
- `uv`
- Node.js 20+ for Wrangler-based preview/deploy
- Terraform 1.6+ for Cloudflare infrastructure
- sibling repo exists at `../broad-listening-book`

## Install

```bash
cd ~/src/broad-listening-book-site
uv sync
```

## Build the web edition

```bash
cd ~/src/broad-listening-book-site
uv run broad-book-build
```

By default this reads content from:

- `../broad-listening-book`

You can override the manuscript path with:

```bash
BOOK_SOURCE_DIR=../some-other-book-repo uv run broad-book-build
```

and writes output to:

- `./site`

You can also run it explicitly:

```bash
uv run python -m broad_listening_book_site.web_build \
  --repo-root ../broad-listening-book \
  --output-dir ./site
```

## Run the dev server

```bash
cd ~/src/broad-listening-book-site
uv run broad-book-site
```

Then open:

- `http://127.0.0.1:8765`

## What it watches

The watcher rebuilds when files change in the manuscript repo, including:

- `*.md`
- `*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`, `*.svg`
- `*.txt`, `*.json`, `*.py`
- `en/`
- `images/`
- `column/`
- `scripts/`
- `memo/`
- `interview_questions/`
- `code/`
- `wip-nishio/`
- `book_order.txt`
- `en/book_order.txt`

Changes under `html/`, `.git/`, and `.venv/` are ignored.

## Health endpoint

```bash
curl http://127.0.0.1:8765/__health
```

This returns current generation/build status.

## Useful flags

```bash
uv run broad-book-site --host 127.0.0.1 --port 8765 --verbose
uv run broad-book-site --skip-initial-build
```

The dev server also honors `BOOK_SOURCE_DIR` if you want to point it at a different manuscript checkout.

## Preview the Cloudflare Worker locally

Build the static site first, then run the Worker with local secrets:

```bash
cd ~/src/broad-listening-book-site
uv run broad-book-build
npm install --ignore-scripts
cp .dev.vars.example .dev.vars
npm run d1:migrate:local
npm run preview:worker
```

On some macOS setups, Wrangler's `miniflare -> sharp` dependency chain fails during the normal npm install script phase even though Wrangler itself still works. In this repo, `npm install --ignore-scripts` is acceptable and was validated with both `wrangler dev` and `wrangler deploy --dry-run`.

Then open:

- `http://127.0.0.1:8787`

The Worker serves `./site`, applies the password gate, sets the signed session cookie, and redirects `www` to the apex host when appropriate.

To clear the session cookie, visit:

- `/logout`

Login POSTs are also rate-limited in the Worker using Cloudflare's rate limiting binding:

- 10 attempts per 60 seconds per client IP, per Cloudflare location

Reader-listening POSTs are rate-limited separately:

- 12 submissions per 60 seconds per client IP, per Cloudflare location

## Reader Listening

Reader listening lets a reader highlight book text, choose `Contribute a perspective`, and submit an anonymous response tied to that passage. It is a private listening record, not a public comment system. Site and book problems still go through GitHub Issues.

The implementation lives in:

- `src/broad_listening_book_site/web_build.py`
  static highlight UI and client-side submit flow
- `worker/src/index.js`
  `/api/listening/submit` and protected export endpoints
- `worker/src/listeningModeration.js`
  deterministic low-cost blocking rules
- `worker/migrations/`
  D1 schema
- `scripts/export-listening.mjs`
  JSONL/CSV export helper
- `spec/LISTEN-PLAN.md`
  product spec and implementation notes

### Local D1 Setup

The local D1 database is created by Wrangler/Miniflare from `wrangler.jsonc`. Apply migrations before testing submissions:

```bash
npm run d1:migrate:local
```

Then run the Worker:

```bash
npm run preview:worker
```

Submit a local smoke-test response:

```bash
curl -sS -X POST "http://127.0.0.1:8787/api/listening/submit" \
  -H "Origin: http://127.0.0.1:8787" \
  -H "Content-Type: application/json" \
  -d '{
    "schemaVersion": 1,
    "lang": "en",
    "pagePath": "/en/01_what_is_broad_listening.html",
    "pageUrl": "http://127.0.0.1:8787/en/01_what_is_broad_listening.html",
    "pageTitle": "Chapter 1: What Is Broad Listening?",
    "chapterId": "01_what_is_broad_listening",
    "chapterTitle": "Chapter 1: What Is Broad Listening?",
    "nearestHeading": "Broad Listening: A Technology for Hearing Many Voices",
    "selectionText": "Broad listening is a technology for hearing the voices of many people.",
    "lens": "missing_voice",
    "responseText": "I would like to hear more from people who are uncomfortable writing in public forms."
  }'
```

Submit a blocked-content smoke test without using offensive language:

```bash
curl -sS -X POST "http://127.0.0.1:8787/api/listening/submit" \
  -H "Origin: http://127.0.0.1:8787" \
  -H "Content-Type: application/json" \
  -d '{
    "schemaVersion": 1,
    "lang": "en",
    "pagePath": "/en/01_what_is_broad_listening.html",
    "pageUrl": "http://127.0.0.1:8787/en/01_what_is_broad_listening.html",
    "pageTitle": "Chapter 1: What Is Broad Listening?",
    "chapterId": "01_what_is_broad_listening",
    "chapterTitle": "Chapter 1: What Is Broad Listening?",
    "nearestHeading": "Broad Listening: A Technology for Hearing Many Voices",
    "selectionText": "Broad listening is a technology for hearing the voices of many people.",
    "lens": "question",
    "responseText": "Please contact me at test@example.com."
  }'
```

The accepted response should return `{"ok":true,...}`. The blocked response should return `{"ok":false,"code":"blocked_content"}`.

### Export Listening Data

Export JSONL from local D1:

```bash
npm run listening:export -- --format jsonl --output listening-exports/local-responses.jsonl
```

Export CSV from the deployed D1 database:

```bash
npm run listening:export -- --remote --format csv --output listening-exports/remote-responses.csv
```

Useful filters:

```bash
npm run listening:export -- --remote --lang ja --since 2026-05-01 --until 2026-05-31
```

Keep exports in `listening-exports/` or another ignored local directory. Do not commit raw response exports.
When querying local D1, run one export at a time; concurrent local D1 reads can briefly hit SQLite lock contention under Wrangler dev.

The Worker also exposes protected HTTP exports:

- `/api/listening/export.jsonl`
- `/api/listening/export.csv`

These require `Authorization: Bearer <LISTENING_EXPORT_TOKEN>`.

## Cloudflare Web Analytics

The Worker can inject the Cloudflare Web Analytics beacon into authenticated HTML pages. This keeps the generated `site/` directory token-free and avoids tracking the password page itself.

To enable it:

1. In Cloudflare, go to Web Analytics and add `broadlisteningbook.com`.
2. Copy the site token from the JavaScript snippet.
3. Set `CLOUDFLARE_WEB_ANALYTICS_TOKEN` in `wrangler.jsonc`.
4. Deploy the Worker.

The injected beacon is Cloudflare's standard script:

```html
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token":"..."}'></script>
```

Cloudflare Web Analytics is JavaScript-based, so it reports browser page views for clients that load pages and run the beacon. The Worker injects the beacon into book HTML and the login page, but not `/logout`.

## Cloudflare Deploy Scaffold

This repo now includes:

- `wrangler.jsonc`
  Worker + static-asset configuration
- `worker/src/`
  custom login flow, cookie signing, auth scopes, robots handling, listening submit/export API
- `worker/migrations/`
  D1 schema migrations
- `infra/cloudflare/`
  Terraform for custom-domain bindings and optional DNSSEC

Expected deploy order:

1. build the site locally
2. preview locally
3. create the production D1 database and replace the placeholder `database_id` in `wrangler.jsonc`
4. apply D1 migrations locally and remotely
5. set Worker secrets with Wrangler
6. deploy the Worker with Wrangler
7. apply Terraform in `infra/cloudflare`

Terraform assumes the Worker service already exists, because the Worker code and secrets are still deployed manually via Wrangler.

Create the production D1 database once:

```bash
npx wrangler d1 create broad-listening-book-listening
```

Copy the returned `database_id` into `wrangler.jsonc`, replacing `00000000-0000-0000-0000-000000000000`, then apply the remote migration:

```bash
npm run d1:migrate:remote
```

Set listening-related secrets when needed:

```bash
npm run cf:secret:listening-export
npm run cf:secret:turnstile
```

`TURNSTILE_SECRET_KEY` is only required if `LISTENING_REQUIRE_TURNSTILE` is set to `true`.

## Post-deploy validation

After `npm run deploy:worker`, record the Worker version printed by Wrangler and the manuscript revision used for the build:

```bash
git -C ../broad-listening-book branch --show-current
git -C ../broad-listening-book log -1 --oneline
```

Then run a small live smoke test against Cloudflare:

```bash
DEPLOY_TAG="$(git -C ../broad-listening-book rev-parse --short HEAD)"

curl -sSL -D /tmp/blb-en-chapter.headers \
  "https://broadlisteningbook.com/en/02_broad_listening_vs_surveys.html?deploy=${DEPLOY_TAG}" \
  -o /tmp/blb-en-chapter.html
rg '^HTTP/' /tmp/blb-en-chapter.headers
rg -o '<title>[^<]+' /tmp/blb-en-chapter.html | head -1
rg -c 'static\.cloudflareinsights\.com/beacon\.min\.js|data-cf-beacon' /tmp/blb-en-chapter.html

curl -sSL "https://broadlisteningbook.com/en/?deploy=${DEPLOY_TAG}" -o /tmp/blb-en-index.html
rg '02_broad_listening_vs_surveys' /tmp/blb-en-index.html | head

encoded_path="$(node -e 'console.log(encodeURI("/ja/01_ブロードリスニングとは何か？"))')"
curl -sSI "https://broadlisteningbook.com${encoded_path}?deploy=${DEPLOY_TAG}" | sed -n '1,10p'

curl -sSL "https://broadlisteningbook.com/en/about.html?deploy=${DEPLOY_TAG}" -o /tmp/blb-en-about.html
curl -sSL "https://broadlisteningbook.com/ja/about.html?deploy=${DEPLOY_TAG}" -o /tmp/blb-ja-about.html
rg 'https://dd2030.org/join-us|https://x.com/lukec' /tmp/blb-en-about.html /tmp/blb-ja-about.html

npm run check:live-images -- --base-url https://broadlisteningbook.com
```

Expected results:

- The English chapter follows Cloudflare's extensionless redirect and ends at `200`.
- The chapter HTML has the expected `<title>` and exactly one Cloudflare Web Analytics beacon match.
- The English index links to the deployed chapter.
- A protected Japanese chapter redirects to `/login` with `X-Robots-Tag: noindex, nofollow, noarchive`.
- English and Japanese About pages are public and include the DD2030 support link and `@lukec` link.
- `check:live-images` reports zero broken image URLs across public crawlable pages. Protected or redirected pages are skipped unless you run the check in an authenticated context.
- A reader-listening POST to `/api/listening/submit` accepts a valid anonymous response.
- A reader-listening POST with blocked content returns `blocked_content`.
- `npm run listening:export -- --remote --format jsonl` returns accepted listening records without committing the export.

## License

This repo is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), matching the manuscript repo. Anyone may freely use, modify, and redistribute it under that license.

## Notes

- HTML responses get a tiny live-reload snippet injected at serve time.
- The manuscript repo remains the content source.
- This repo owns the web-edition builder and dev workflow.
- Generated output stays inside this repo by default.
