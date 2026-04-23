variable "cloudflare_account_id" {
  description = "Cloudflare account ID that owns the zone and Worker."
  type        = string
}

variable "zone_name" {
  description = "Cloudflare zone name for the site."
  type        = string
  default     = "broadlisteningbook.com"
}

variable "worker_service_name" {
  description = "Name of the deployed Cloudflare Worker service."
  type        = string
  default     = "broad-listening-book-site"
}

variable "apex_hostname" {
  description = "Apex hostname to bind to the Worker. Leave blank to use the zone name."
  type        = string
  default     = ""
}

variable "www_hostname" {
  description = "WWW hostname to bind to the Worker. Leave blank to use www.<zone_name>."
  type        = string
  default     = ""
}

variable "enable_www_custom_domain" {
  description = "Whether to attach the www hostname to the Worker."
  type        = bool
  default     = true
}

variable "enable_dnssec" {
  description = "Whether Terraform should enable DNSSEC on the zone."
  type        = bool
  default     = false
}
