terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  for_each = toset(var.aws_regions)
  region   = each.value
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

resource "aws_key_pair" "keypair" {
  for_each   = toset(var.aws_regions)
  key_name   = "${var.app_name}-key-pair-${each.value}"
  public_key = file(var.public_key)
  provider   = aws[each.value]
}

module "networkModule" {
  for_each = toset(var.aws_regions)
  source   = "./modules/network"
  app_name = var.app_name
  region   = each.value
  provider = aws[each.value]

  cidr_block_range         = "10.0.0.0/16"
  subnet1_cidr_block_range = "10.0.1.0/24"
  subnet2_cidr_block_range = "10.0.2.0/24"
}

module "securityGroupModule" {
  for_each = toset(var.aws_regions)
  source   = "./modules/securityGroup"
  provider = aws[each.value]

  vpc_id   = module.networkModule[each.value].vpc_id
  app_name = var.app_name
}

module "instanceModule" {
  for_each = toset(var.aws_regions)
  source   = "./modules/instance"
  provider = aws[each.value]

  count               = var.instances_per_region
  instance_type       = var.aws_instance_type
  region              = each.value
  vpc_id              = module.networkModule[each.value].vpc_id
  subnet_public_id    = module.networkModule[each.value].public_subnets[0]
  security_group_ids  = [module.securityGroupModule[each.value].sg_22]
  app_name            = var.app_name

  orchestrator_config_path = var.orchestrator_config_path
  bacalhau_installation_id = var.bacalhau_installation_id
  key_pair_name            = aws_key_pair.keypair[each.value].key_name
  username                 = var.username
  public_key               = var.public_key
  logs_dir                 = var.logs_dir
  logs_to_process_dir      = var.logs_to_process_dir
  central_logging_bucket   = var.central_logging_bucket
}

