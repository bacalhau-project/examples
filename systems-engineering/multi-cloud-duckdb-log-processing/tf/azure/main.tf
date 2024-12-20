terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.app_tag}-resource-group"
  location = var.region
}

module "networkModule" {
  source = "./modules/network"

  resource_group_name = azurerm_resource_group.rg.name
  location           = var.region
  app_tag            = var.app_tag
}

module "securityGroupModule" {
  source = "./modules/securityGroup"

  resource_group_name = azurerm_resource_group.rg.name
  location           = var.region
  app_tag            = var.app_tag
}

module "instanceModule" {
  source = "./modules/instance"

  resource_group_name  = azurerm_resource_group.rg.name
  location            = var.region
  app_tag             = var.app_tag
  vm_size             = var.vm_size
  subnet_id           = module.networkModule.subnet_id
  nsg_id              = module.securityGroupModule.nsg_id
  bacalhau_run_file   = var.bacalhau_run_file
  bootstrap_region    = var.bootstrap_region
  admin_username      = var.admin_username
  public_key         = var.public_key
  private_key        = var.private_key
  tailscale_key      = var.tailscale_key
}
