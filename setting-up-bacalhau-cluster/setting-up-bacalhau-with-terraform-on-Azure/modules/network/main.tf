resource "azurerm_virtual_network" "vnet" {
  name                = "${var.app_tag}-${var.location}-network"
  address_space       = ["10.0.0.0/16"]
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = {
    App = var.app_tag
  }
}

resource "azurerm_subnet" "subnet" {
  name                 = "${var.app_tag}-${var.location}-subnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}
