# Infrastructure

Cloudflare infrastructure for the book site lives in [cloudflare](./cloudflare/).

The intended split is:

- Wrangler deploys the Worker code, static assets, and Worker secrets.
- Terraform manages Cloudflare account/zone resources around that Worker where practical.
