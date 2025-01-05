output "public_ips" {
  description = "Public IPs of the instances"
  value       = module.instanceModule[*].public_ip
}

output "private_ips" {
  description = "Private IPs of the instances"
  value       = module.instanceModule[*].private_ip
}

output "instance_ids" {
  description = "IDs of the created instances"
  value       = module.instanceModule[*].instance_id
}
