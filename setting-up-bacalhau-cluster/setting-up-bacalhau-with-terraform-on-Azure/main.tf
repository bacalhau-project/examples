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
  timestamp             = formatdate("YYMMDDHHmm", timestamp())
  resource_group_name   = var.resource_group_name != null && var.resource_group_name != "" ? var.resource_group_name : "${var.app_tag}-${local.timestamp}"
  create_resource_group = var.resource_group_name == null || var.resource_group_name == ""
}

data "azurerm_resource_group" "existing" {
  count = local.create_resource_group ? 0 : 1
  name  = local.resource_group_name
}

resource "azurerm_resource_group" "rg" {
  count    = local.create_resource_group ? 1 : 0
  name     = local.resource_group_name
  location = var.resource_group_region
}

locals {
  effective_resource_group_name = local.create_resource_group ? azurerm_resource_group.rg[0].name : data.azurerm_resource_group.existing[0].name
}

module "networkModule" {
  for_each = var.locations
  source   = "./modules/network"

  resource_group_name = local.effective_resource_group_name
  location            = each.key
  app_tag             = var.app_tag
}

module "securityGroupModule" {
  for_each = var.locations
  source   = "./modules/securityGroup"

  resource_group_name = local.effective_resource_group_name
  location            = each.key
  app_tag             = var.app_tag
}

module "instanceModule" {
  for_each = var.locations
  source   = "./modules/instance"

  resource_group_name  = local.effective_resource_group_name
  location             = each.key
  app_tag              = var.app_tag
  vm_size              = each.value.machine_type
  subnet_id            = module.networkModule[each.key].subnet_id
  nsg_id               = module.securityGroupModule[each.key].nsg_id
  username             = var.username
  public_ssh_key_path  = var.public_ssh_key_path
  node_count           = each.value.node_count
  bacalhau_config_file = filebase64("${path.module}/${var.bacalhau_config_file_path}")
  data_disk_size_gb    = var.data_disk_size_gb
}
