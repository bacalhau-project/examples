output "public_ip" {
  value = [for eip in aws_eip.instanceeip : eip.public_ip]
}

output "private_ip" {
  value = [for eip in aws_eip.instanceeip : eip.private_ip]
}

output "instance_id" {
  value = [for instance in aws_instance.instance : instance.id]
}

output "instance_name" {
  description = "The generated names of the instances"
  value       = local.vm_names
}
