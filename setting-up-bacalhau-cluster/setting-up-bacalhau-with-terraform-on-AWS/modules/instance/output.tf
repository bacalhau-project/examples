output "public_ip" {
  value = aws_eip.instanceeip.public_ip
}

output "private_ip" {
  value = aws_eip.instanceeip.private_ip
}

output "instance_id" {
  value = aws_instance.instance.id
}

output "instance_name" {
  description = "The generated name of the instance"
  value       = local.vm_name
}
