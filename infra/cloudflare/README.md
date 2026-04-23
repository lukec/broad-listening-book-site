# Cloudflare Terraform

This directory manages the Cloudflare-side resources around the book site deployment.

Current scope:

- look up the existing `broadlisteningbook.com` zone
- attach the deployed Worker service to the apex custom domain
- optionally attach the `www` hostname to the same Worker so the Worker can redirect it to the apex host
- optionally enable DNSSEC

This Terraform does **not** manage:

- Worker code deployment
- Worker secrets
- shared password values
- cookie signing secrets
- Terraform remote state

## Assumptions

Before `terraform apply`, do this first:

1. build the static site
2. deploy the Worker once with Wrangler so the Worker service exists
3. know your Cloudflare account ID

The Worker service name defaults to `broad-listening-book-site`, matching `wrangler.jsonc`.

## Inputs

Copy the example file and fill it in:

```bash
cd infra/cloudflare
cp terraform.tfvars.example terraform.tfvars
```

Expected inputs:

- `cloudflare_account_id`
- `zone_name`
- optional `enable_www_custom_domain`
- optional `enable_dnssec`

## Commands

```bash
cd infra/cloudflare
terraform init
terraform plan
terraform apply
```

If you manually add a Worker custom domain in the dashboard first, import it into Terraform before applying here.
