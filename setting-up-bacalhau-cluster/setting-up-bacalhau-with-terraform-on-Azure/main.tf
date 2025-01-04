terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  timestamp           = formatdate("YYMMDDHHmm", timestamp())
  resource_group_name = "${var.app_tag}-${local.timestamp}"
}

resource "azurerm_resource_group" "rg" {
  name     = local.resource_group_name
  location = var.resource_group_region
}

module "networkModule" {
  for_each = var.locations
  source   = "./modules/network"

  resource_group_name = azurerm_resource_group.rg.name
  location            = each.key
  app_tag             = var.app_tag
}

module "securityGroupModule" {
  for_each = var.locations
  source   = "./modules/securityGroup"

  resource_group_name = azurerm_resource_group.rg.name
  location            = each.key
  app_tag             = var.app_tag
}

module "instanceModule" {
  for_each = var.locations
  source   = "./modules/instance"

  resource_group_name  = azurerm_resource_group.rg.name
  location             = each.key
  app_tag              = var.app_tag
  vm_size              = each.value.machine_type
  subnet_id            = module.networkModule[each.key].subnet_id
  nsg_id               = module.securityGroupModule[each.key].nsg_id
  username             = var.username
  public_key           = var.public_key
  node_count           = each.value.node_count
  bacalhau_config_file = filebase64("${path.module}/config/config.yaml")
}
