output "public_ips" {
  description = "Public IP addresses of the VMs"
  value       = azurerm_linux_virtual_machine.vm[*].public_ip_address
}

output "private_ips" {
  description = "Private IP addresses of the VMs"
  value       = azurerm_linux_virtual_machine.vm[*].private_ip_address
}

output "node_count" {
  description = "Number of nodes created"
  value       = var.node_count
}

output "health_status" {
  description = "Health check status for each VM"
  value = {
    for idx in range(var.node_count) : azurerm_linux_virtual_machine.vm[idx].name => {
      public_ip    = azurerm_linux_virtual_machine.vm[idx].public_ip_address
      private_ip   = azurerm_linux_virtual_machine.vm[idx].private_ip_address
      health_check = try(data.http.healthcheck[idx].status_code == 200, false) ? "healthy" : "unhealthy"
      status_code  = try(data.http.healthcheck[idx].status_code, null)
    }
  }
}
