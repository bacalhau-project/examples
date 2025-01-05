output "public_ips" {
  description = "Public IPs of the instances"
  value       = module.region[*].public_ips
}

output "private_ips" {
  description = "Private IPs of the instances"
  value       = module.region.private_ips
}

output "instance_ids" {
  description = "IDs of the created instances"
  value       = module.region.instance_ids
}
