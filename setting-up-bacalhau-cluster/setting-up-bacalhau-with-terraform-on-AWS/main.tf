# Check if AWS credentials are properly configured
data "aws_caller_identity" "current" {
  provider = aws.us_east_1 # Use a default provider for the check
}

module "region" {
  source = "./modules/region"

  region                    = var.region
  zone                      = var.zone
  instance_ami              = var.instance_ami
  node_count                = var.node_count
  app_tag                   = var.app_tag
  aws_instance_type         = var.instance_type
  public_key                = var.public_key
  private_key               = var.private_key
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

output "instance_public_ips" {
  value = module.region.public_ips
}
