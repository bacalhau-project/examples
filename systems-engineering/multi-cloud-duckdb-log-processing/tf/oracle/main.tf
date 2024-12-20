terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 4.0"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

module "networkModule" {
  source = "./modules/network"

  compartment_id = var.compartment_id
  region         = var.region
  app_tag        = var.app_tag
}

module "securityGroupModule" {
  source = "./modules/securityGroup"

  compartment_id = var.compartment_id
  vcn_id         = module.networkModule.vcn_id
  app_tag        = var.app_tag
}

module "instanceModule" {
  source = "./modules/instance"

  compartment_id     = var.compartment_id
  region            = var.region
  app_tag           = var.app_tag
  instance_shape    = var.instance_shape
  subnet_id         = module.networkModule.subnet_id
  nsg_ids           = [module.securityGroupModule.nsg_id]
  bacalhau_run_file = var.bacalhau_run_file
  bootstrap_region  = var.bootstrap_region
  ssh_user         = var.ssh_user
  public_key       = var.public_key
  private_key      = var.private_key
  tailscale_key    = var.tailscale_key
}
