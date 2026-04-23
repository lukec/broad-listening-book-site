# Broad Listening Book Site Launch Plan

## Goal

Launch a polished web edition of the Broad Listening book on:

- `https://broadlisteningbook.com/`

with these constraints:

- initial launch is behind a shared password
- later launch exposes the English site publicly while keeping `/ja/` protected
- the site repo stays public
- the manuscript content remains sourced from the sibling manuscript repo, not copied into this repo
- deploys are manual from a local machine
- infrastructure is managed with Terraform where practical

## Current Repo Role

This repo is the site/build/deploy repo.

It already owns:

- the HTML web-book builder
- the local live-reload dev server
- generation of the pretty multilingual static site into `./site`

It should not own:

- the manuscript markdown
- generated manuscript source copies
- passwords, signing keys, API tokens, or Terraform state

## Source of Truth

The manuscript source stays in the sibling repo:

- default path: `../broad-listening-book`

The site repo should:

- assume that sibling path by default
- allow an override via environment variable such as `BOOK_SOURCE_DIR`
- fail clearly if the manuscript repo is missing

## Hosting Architecture

Recommended production architecture:

- `Cloudflare Worker + Static Assets`
- custom domain on `broadlisteningbook.com`
- `www.broadlisteningbook.com` redirects to apex

Reasoning:

- supports a custom branded login page
- supports path-based protection later (`/ja/*`)
- keeps the site fully static
- avoids needing AWS/Lambda for a simple password-gated launch
- fits manual local deploys well via Wrangler

## Authentication Model

Use a Worker-based custom login flow, not browser-native Basic Auth.

Requirements:

- fixed username
- shared password
- branded login page that matches the book design
- successful login issues a signed `HttpOnly` cookie
- cookie lifetime: 30 days

Phase 1 auth scope:

- protect all paths

Phase 2 auth scope:

- public: `/`, `/en/*`, shared static assets as needed
- protected: `/ja/*`

Suggested implementation shape:

- Worker checks request path against protection mode
- unauthenticated requests redirect to `/login`
- `/login` renders branded HTML
- successful POST to `/login` sets signed session cookie and redirects back
- logout endpoint clears cookie

## Search Engine Blocking

Initial launch should block search engines.

Use multiple layers:

- `X-Robots-Tag: noindex, nofollow, noarchive`
- `robots.txt` with `Disallow: /`
- `<meta name="robots" content="noindex,nofollow">` on the login page

When English becomes public later, revisit:

- allow indexing for public English pages
- keep `/ja/` blocked and gated

## Repository / Security Rules

This repo is public, so it must never contain secrets.

Do not commit:

- shared password
- cookie signing secret
- Cloudflare API token
- `.dev.vars`
- `.env`
- Terraform state
- Terraform variable files containing secrets

Do not commit manuscript content into this repo.

Safe to commit:

- Worker source code
- Terraform configuration in `infra/`
- build scripts
- deploy scripts
- documentation

Rationale:

- the manuscript is already public in the manuscript repo
- this repo should remain a clean site/deployment repo
- public infra/app code is fine as long as secrets stay out of git

## Terraform Responsibilities

Terraform should live in:

- `infra/`

Terraform should manage:

- Cloudflare resources for the site
- Worker custom domain bindings
- DNS records that belong to this site rollout
- `www` to apex redirect resources if implemented at the platform layer

Terraform should not manage:

- the shared password
- cookie signing secret
- local deploy credentials

Those should be Worker secrets set outside Terraform, because putting them in Terraform usually means putting them in state.

Note:

- the Cloudflare zone may be created/activated manually in the dashboard first
- Terraform can then target the existing zone by ID / data source or via import

## Wrangler Responsibilities

Wrangler should handle:

- local auth to the Cloudflare account
- manual Worker deploys
- uploading static assets
- setting Worker secrets

Likely local commands:

```bash
npm i -D wrangler@latest
npx wrangler login
npx wrangler secret put SHARED_PASSWORD
npx wrangler secret put COOKIE_SIGNING_SECRET
npx wrangler deploy
```

Exact commands may vary once the Worker app is scaffolded.

## Build / Deploy Workflow

Build and deploy should remain separate steps.

Build:

- read manuscript from `../broad-listening-book` by default
- allow `BOOK_SOURCE_DIR` override
- generate static site into this repo's build output directory, currently `./site`

Deploy:

- publish the built static output via Cloudflare Worker static assets
- do not rebuild implicitly unless explicitly requested

Recommended manual release flow:

1. build locally
2. inspect locally
3. deploy manually

## Proposed Repo Additions

### Worker App

Add a Worker app that:

- serves static assets from the generated site output
- renders the branded login page
- validates username/password
- issues and validates signed auth cookies
- supports two protection modes:
  - `all`
  - `ja-only`
- adds search-blocking headers as needed

### Config

Add config for:

- manuscript source directory default
- site output directory
- auth protection mode
- cookie lifetime
- canonical domain

Likely non-secret config can live in:

- `wrangler.toml` or `wrangler.jsonc`
- Python/JS config files

Secret config must remain in Worker secrets.

### Infra

Add:

- `infra/README.md`
- Terraform configuration for Cloudflare resources
- documented manual `terraform init/plan/apply` workflow

## Branded Login Page

The login page should visually match the book site.

Design direction:

- reuse the existing typography and layout language from the book site
- include the title and draft/pre-release framing if useful
- minimal form:
  - fixed username field or hidden fixed username
  - password field
  - submit button
- clear but understated message that this is a preview/review release

Open implementation detail:

- fixed username can be hardcoded or lightly shown on the form
- exact value does not matter much

## Suggested Directory Shape

One likely structure:

```text
infra/
  cloudflare/
src/
  broad_listening_book_site/
worker/
  src/
  public/
scripts/
site/
PLAN.md
```

The exact layout can change, but the important separation is:

- Python builder/dev-server code
- Worker/auth app
- Terraform infra
- generated site output

## Rollout Phases

### Phase 0: Prep

- user creates Cloudflare account
- add `broadlisteningbook.com` zone to Cloudflare
- review imported DNS records
- turn off DNSSEC at registrar if needed
- switch nameservers at Name.com to Cloudflare nameservers
- wait for zone activation

### Phase 1: Protected Preview Launch

- deploy full site behind login
- block search engines
- manual deploy only
- share password privately with DD2030 reviewers

### Phase 2: Public English / Protected Japanese

- switch auth mode from `all` to `ja-only`
- keep `/ja/*` gated
- decide whether to remove `noindex` from public English pages

## Immediate Implementation Checklist

1. Scaffold `infra/` Terraform for Cloudflare resources
2. Scaffold Worker app with custom login flow
3. Add Worker static-asset serving
4. Add cookie signing and validation
5. Add auth-mode switch: `all` vs `ja-only`
6. Add `robots.txt` and noindex headers
7. Wire build output from current Python builder into deployable asset directory
8. Add `.gitignore` rules for secrets and Terraform state
9. Add manual deploy documentation
10. Test local build -> local preview -> Cloudflare deploy

## Local Development Assumptions

For now:

- deploys are run from the local machine only
- no GitHub Actions deployment flow is required
- fixed sibling manuscript path is acceptable
- env override remains useful for flexibility

## Open Decisions Remaining

These are still implementation details, not blockers:

- exact fixed username value
- exact Worker/framework choice:
  - plain Worker
  - Worker with a small router/framework
- whether `www -> apex` is implemented by:
  - Cloudflare redirect rule
  - Worker logic
- whether generated `site/` output stays uncommitted or is selectively committed

## Recommended Defaults

Unless requirements change, use:

- manuscript repo default path: `../broad-listening-book`
- env override: `BOOK_SOURCE_DIR`
- build output: `./site`
- canonical URL: `https://broadlisteningbook.com/`
- `www` redirects to apex
- auth cookie lifetime: 30 days
- initial auth scope: `all`
- later auth scope: `ja-only`
- search indexing: blocked during protected preview

## Summary

The plan is to keep this repo as a public, secret-free site/deploy repo that builds from the sibling manuscript repo, then deploy a Cloudflare Worker-based static site with a branded password gate.

This gives us:

- a clean repo boundary
- no secret leakage into git
- manual, controllable releases
- a simple path from full-site preview gating to Japanese-only protection later
