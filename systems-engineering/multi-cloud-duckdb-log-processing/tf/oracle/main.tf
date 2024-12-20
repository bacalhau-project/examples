terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 4.0"
    }
  }
}

provider "oci" {
  tenancy_ocid = var.oci_tenancy_ocid
  region       = var.oci_regions[0]  # Use first region as default
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

module "networkModule" {
  for_each = toset(var.oci_regions)
  source   = "./modules/network"

  compartment_id = var.oci_tenancy_ocid
  region         = each.value
  app_name       = var.app_name
}

module "securityGroupModule" {
  for_each = toset(var.oci_regions)
  source   = "./modules/securityGroup"

  compartment_id = var.oci_tenancy_ocid
  vcn_id         = module.networkModule[each.value].vcn_id
  app_name       = var.app_name
}

module "instanceModule" {
  for_each = toset(var.oci_regions)
  source   = "./modules/instance"

  count               = var.instances_per_region
  compartment_id      = var.oci_tenancy_ocid
  region              = each.value
  app_name            = var.app_name
  instance_shape      = var.oci_instance_shape
  subnet_id           = module.networkModule[each.value].subnet_id
  nsg_ids             = [module.securityGroupModule[each.value].nsg_id]
  orchestrator_config_path = var.orchestrator_config_path
  bacalhau_installation_id = var.bacalhau_installation_id
  username            = var.username
  public_key          = var.public_key
  logs_dir            = var.logs_dir
  logs_to_process_dir = var.logs_to_process_dir
  central_logging_bucket = var.central_logging_bucket
}

resource "oci_objectstorage_bucket" "bucket" {
  count           = var.buckets_per_region * length(var.oci_regions)
  compartment_id  = var.oci_tenancy_ocid
  name            = "${var.app_name}-${var.oci_regions[floor(count.index / var.buckets_per_region)]}-bucket-${count.index % var.buckets_per_region + 1}"
  namespace       = data.oci_objectstorage_namespace.ns.namespace
  storage_tier    = "Archive"
  versioning      = "Enabled"
}

data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.oci_tenancy_ocid
}
