output "public_ips" {
  description = "Public IPs of the instances"
  value       = aws_eip.instanceeip[*].public_ip
}

output "private_ips" {
  description = "Private IPs of the instances"
  value       = aws_eip.instanceeip[*].private_ip
}

output "instance_ids" {
  description = "IDs of the created instances"
  value       = aws_instance.instance[*].id
}

output "instance_names" {
  description = "The generated names of the instances"
  value       = local.vm_names
}
