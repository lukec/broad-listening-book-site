# broad-listening-book-site

Tooling repo for a pretty web version of the Broad Listening book.

This repo now owns the fancy multilingual HTML book build and the local live-reload dev server for the sibling manuscript repo at `../broad-listening-book`.

It does two main things:

1. builds the web edition from manuscript content in `../broad-listening-book`
2. serves its own generated `site/` directory, watches manuscript changes, and live-reloads browser tabs

## Requirements

- Python 3.10+
- `uv`
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

## License

This repo follows the same license as the manuscript repo: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Notes

- HTML responses get a tiny live-reload snippet injected at serve time.
- The manuscript repo remains the content source.
- This repo owns the web-edition builder and dev workflow.
- Generated output stays inside this repo by default.
