terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.75.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

locals {
  required_files = {
    bacalhau_service    = fileexists("${path.module}/node_files/bacalhau.service")
    start_bacalhau      = fileexists("${path.module}/node_files/start_bacalhau.sh")
    orchestrator_config = fileexists(var.orchestrator_config_path)
  }

  missing_files = [for name, exists in local.required_files : name if !exists]

  validate_files = length(local.missing_files) == 0 ? true : tobool(
    "Missing required files: ${join(", ", local.missing_files)}"
  )
}

resource "azurerm_resource_group" "rg" {
  for_each = toset(var.azure_regions)
  name     = "${var.app_name}-${each.value}-rg"
  location = each.value
}

module "networkModule" {
  for_each = toset(var.azure_regions)
  source   = "./modules/network"

  resource_group_name = azurerm_resource_group.rg[each.value].name
  location           = each.value
  app_name           = var.app_name
}

module "securityGroupModule" {
  for_each = toset(var.azure_regions)
  source   = "./modules/securityGroup"

  resource_group_name = azurerm_resource_group.rg[each.value].name
  location           = each.value
  app_name           = var.app_name
}

module "instanceModule" {
  for_each = toset(var.azure_regions)
  source   = "./modules/instance"

  count                   = var.instances_per_region
  resource_group_name     = azurerm_resource_group.rg[each.value].name
  location               = each.value
  app_name               = var.app_name
  vm_size                = var.azure_vm_size
  subnet_id              = module.networkModule[each.value].subnet_id
  nsg_id                 = module.securityGroupModule[each.value].nsg_id
  orchestrator_config_path = var.orchestrator_config_path
  bacalhau_installation_id = var.bacalhau_installation_id
  username               = var.username
  public_key             = var.public_key
  logs_dir              = var.logs_dir
  logs_to_process_dir   = var.logs_to_process_dir
  central_logging_bucket = var.central_logging_bucket
}

resource "azurerm_storage_account" "storage" {
  count                    = var.buckets_per_region * length(var.azure_regions)
  name                     = "${lower(var.app_name)}${count.index + 1}"
  resource_group_name      = azurerm_resource_group.rg[var.azure_regions[floor(count.index / var.buckets_per_region)]].name
  location                 = var.azure_regions[floor(count.index / var.buckets_per_region)]
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
