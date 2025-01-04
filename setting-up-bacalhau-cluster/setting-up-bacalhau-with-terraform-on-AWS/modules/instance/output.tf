output "public_ip" {
  value = aws_eip.instanceeip[*].public_ip
}

output "private_ip" {
  value = aws_eip.instanceeip[*].private_ip
}

output "instance_id" {
  value = aws_instance.instance[*].id
}

output "instance_name" {
  description = "The generated names of the instances"
  value       = local.vm_names
}
