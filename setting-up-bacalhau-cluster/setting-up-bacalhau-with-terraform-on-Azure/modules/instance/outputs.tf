output "public_ips" {
  description = "Public IP addresses of the VMs"
  value       = azurerm_public_ip.pip[*].ip_address
}

output "private_ips" {
  description = "Private IP addresses of the VMs"
  value       = azurerm_network_interface.nic[*].private_ip_address
}

output "node_count" {
  description = "Number of nodes created"
  value       = var.node_count
} 
