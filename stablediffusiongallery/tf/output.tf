output "base_domain_nameservers" {
  value = module.dnsModule.domain_name_servers
}

output "ip_address" {
  value = module.instanceModule.instance_eip
}

output "public_dns" {
  value = module.dnsModule.domain_name
}
