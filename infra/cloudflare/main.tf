data "cloudflare_zones" "site" {
  name = var.zone_name
  account = {
    id = var.cloudflare_account_id
  }
}

locals {
  zone          = one(data.cloudflare_zones.site.result)
  zone_id       = local.zone.id
  apex_hostname = trimspace(var.apex_hostname) != "" ? trimspace(var.apex_hostname) : var.zone_name
  www_hostname  = trimspace(var.www_hostname) != "" ? trimspace(var.www_hostname) : "www.${var.zone_name}"
}

resource "cloudflare_workers_custom_domain" "apex" {
  account_id  = var.cloudflare_account_id
  environment = "production"
  hostname    = local.apex_hostname
  service     = var.worker_service_name
  zone_id     = local.zone_id
}

resource "cloudflare_workers_custom_domain" "www" {
  count       = var.enable_www_custom_domain ? 1 : 0
  account_id  = var.cloudflare_account_id
  environment = "production"
  hostname    = local.www_hostname
  service     = var.worker_service_name
  zone_id     = local.zone_id
}

resource "cloudflare_zone_dnssec" "site" {
  count   = var.enable_dnssec ? 1 : 0
  zone_id = local.zone_id
  status  = "active"
}
