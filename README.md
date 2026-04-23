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

Cloudflare Web Analytics is JavaScript-based, so it reports browser page views for readers who load the authenticated pages and run the beacon. It will not count the password form, `/logout`, or clients that block the beacon script.

## Cloudflare Deploy Scaffold

This repo now includes:

- `wrangler.jsonc`
  Worker + static-asset configuration
- `worker/src/`
  custom login flow, cookie signing, auth scopes, robots handling
- `infra/cloudflare/`
  Terraform for custom-domain bindings and optional DNSSEC

Expected deploy order:

1. build the site locally
2. preview locally
3. set Worker secrets with Wrangler
4. deploy the Worker with Wrangler
5. apply Terraform in `infra/cloudflare`

Terraform assumes the Worker service already exists, because the Worker code and secrets are still deployed manually via Wrangler.

## License

This repo is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), matching the manuscript repo. Anyone may freely use, modify, and redistribute it under that license.

## Notes

- HTML responses get a tiny live-reload snippet injected at serve time.
- The manuscript repo remains the content source.
- This repo owns the web-edition builder and dev workflow.
- Generated output stays inside this repo by default.
