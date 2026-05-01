# AGENTS.md

This repository is the implementation and deployment repo for the Broad Listening book web edition.

It is intentionally separate from the sibling manuscript repo at `../broad-listening-book`, which remains the source of truth for manuscript content.

If you are an agent working here, optimize for:

- clean separation between manuscript, site build, and deploy infrastructure
- inspectable static output
- reproducible local build and preview workflows
- a public, secret-free repository
- a straightforward path to manual Cloudflare deploys

## First Orientation

Start with:

1. [README.md](./README.md)
2. [PLAN.md](./PLAN.md)
3. this file
4. `src/broad_listening_book_site/web_build.py`
5. `src/broad_listening_book_site/server.py`

When content or manuscript structure matters, read from the sibling repo:

- `../broad-listening-book/AGENTS.md`
- the relevant markdown, image, and `book_order.txt` files in `../broad-listening-book`

## Repo Role

This repo currently owns:

- the multilingual HTML book builder
- the local live-reload preview server
- generation of the static site output in `./site`

This repo is also the planned home for:

- Cloudflare Worker application code
- password-gate/auth logic
- Terraform configuration for Cloudflare resources
- deploy documentation and scripts

This repo should not own:

- copied manuscript source files
- long-lived duplicate content
- shared passwords, cookie secrets, API tokens, or Terraform state
- hidden deploy side effects that rebuild implicitly

## Current Layout

- `src/broad_listening_book_site/web_build.py`
  builder for the multilingual static web edition
- `src/broad_listening_book_site/server.py`
  local dev server with file watching and live reload
- `src/broad_listening_book_site/cli.py`
  console entrypoint
- `site/`
  generated output, ignored by git
- `PLAN.md`
  launch and deployment plan, especially for Cloudflare architecture

If `worker/`, `infra/`, or `scripts/` are added, keep their responsibilities explicit and narrow rather than blending build, auth, and infrastructure concerns together.

## Working Rules

### 1. Keep The Manuscript Boundary Clean

- The manuscript source lives in `../broad-listening-book`.
- Default to that sibling path unless a clear config override is being added.
- If configurability changes, expose it through a flag or config surface rather than scattering path edits through the codebase.
- Fail clearly when the manuscript repo is missing or incomplete.

### 2. Keep Build And Deploy Separate

- `broad-book-build` should build the site output and stop there.
- Local preview should serve already-built output and rebuild only when explicitly in dev-server mode.
- Future deploy commands should publish existing build output instead of quietly rebuilding during deploy.

This repo is following a manual release model for now:

1. build locally
2. inspect locally
3. deploy manually

### 3. Treat This As A Public Repo

- Never commit secrets.
- Keep `.env`, `.dev.vars`, Terraform state, and secret-bearing variable files out of git.
- Use Wrangler secrets or equivalent secret storage for shared-password and cookie-signing values.
- Do not commit manuscript copies into this repo just to simplify build steps.

### 4. Preserve The Editorial Reading Experience

This is a book-reading surface, not a dashboard or generic marketing site.

- Preserve the intentional editorial feel of the current HTML output.
- Keep multilingual navigation simple and obvious.
- Avoid generic app UI patterns that make the site feel like a SaaS control panel.
- If you change layout or styling, verify the result on both desktop and mobile reading widths.

### 5. Default To Real, Narrow Implementations

- Prefer a working Cloudflare Worker auth path over speculative framework setup.
- Prefer a real deploy script or README section over placeholder automation.
- Keep Python build logic, Worker/auth logic, and Terraform code in separate boundaries.

### 6. Keep Durable Knowledge In The Right Repo

- Manuscript and book-writing conventions belong in the sibling manuscript repo.
- Site build, preview, deployment, and hosting implementation belong here.

## Verification

When changing code in this repo, verify at the repo level when practical:

- `uv sync`
- `uv run broad-book-build`
- `uv run broad-book-site`
- `curl http://127.0.0.1:8765/__health`

If a change affects rendering, inspect the generated `site/` pages in a browser.

When Worker and Terraform code are added, extend this section with exact verification commands instead of leaving them implicit.

After deploying to Cloudflare, run the `README.md` post-deploy validation checklist and report:

- manuscript branch and commit used for the build
- Worker version ID printed by Wrangler
- public English page/index checks
- protected Japanese redirect and `X-Robots-Tag` check
- About page support-link checks

## Editing Guidance

- Prefer small, inspectable changes over broad rewrites.
- Keep comments sparse and useful.
- Keep generated `site/` output out of git unless the release model explicitly changes.
- Keep deployment docs accurate to the actual manual workflow.
- If you learn a durable repo-specific lesson while working here, update this file so follow-up sessions inherit it.
