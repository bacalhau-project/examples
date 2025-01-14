# Configure the AWS Provider for the current workspace/region


provider "aws" {
  region                   = var.region
  shared_config_files      = ["~/.aws/config"]
  shared_credentials_files = ["~/.aws/credentials"]
}

# Create a unique identifier for this zone deployment
locals {
  zone_id = "${var.region}-${var.zone}"
}

module "region" {
  source = "./modules/region"

  region                    = var.region
  zone                      = var.zone
  instance_ami              = var.instance_ami
  node_count                = var.node_count
  app_tag                   = "${var.app_tag}-${local.zone_id}"
  aws_instance_type         = var.instance_type
  public_key_path           = var.public_key_path
  private_key_path          = var.private_key_path
  app_name                  = var.app_name
  bacalhau_installation_id  = var.bacalhau_installation_id
  bacalhau_data_dir         = var.bacalhau_data_dir
  bacalhau_node_dir         = var.bacalhau_node_dir
  bacalhau_config_file_path = var.bacalhau_config_file_path
  username                  = var.username

  providers = {
    aws = aws
  }
}
