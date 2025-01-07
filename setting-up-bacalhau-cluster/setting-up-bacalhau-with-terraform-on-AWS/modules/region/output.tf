output "public_ips" {
  description = "Public IPs of the instances"
  value       = module.instanceModule.public_ips
}

output "private_ips" {
  description = "Private IPs of the instances"
  value       = module.instanceModule.private_ips
}

output "instance_ids" {
  description = "IDs of the created instances"
  value       = module.instanceModule.instance_ids
}

output "instance_names" {
  description = "Names of all created instances"
  value       = module.instanceModule.instance_names
}
