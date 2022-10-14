provider "aws" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

module "dnsModule" {
  source      = "./modules/dns"
  access_key  = var.access_key
  secret_key  = var.secret_key
  region      = var.region
  domain_name = "${var.domain_name}"
  aRecords = [
    "${var.domain_name} ${var.instance_eip}",
  ]
  cnameRecords = [
    "www.${var.domain_name} ${var.domain_name}"
  ]
  app_tag    = var.app_tag
}
