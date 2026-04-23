output "zone_id" {
  description = "Resolved Cloudflare zone ID."
  value       = local.zone_id
}

output "worker_service_name" {
  description = "Worker service name bound by this Terraform."
  value       = var.worker_service_name
}

output "apex_custom_domain_hostname" {
  description = "Apex hostname attached to the Worker."
  value       = cloudflare_workers_custom_domain.apex.hostname
}

output "www_custom_domain_hostname" {
  description = "WWW hostname attached to the Worker when enabled."
  value       = var.enable_www_custom_domain ? cloudflare_workers_custom_domain.www[0].hostname : null
}
