output "ip_addresses" {
  value = data.azurerm_public_ip.public_ip.*
}
