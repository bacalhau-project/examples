provider "aws" {
  alias  = "primary"
  region = keys(var.locations)[0]
  
  # Configure for SSO credentials
  shared_config_files      = ["~/.aws/config"]
  shared_credentials_files = ["~/.aws/credentials"]
}

# Check if AWS credentials are properly configured
data "aws_caller_identity" "current" {}

module "regions" {
  for_each = var.locations

  source = "./modules/region"

  region                    = each.key
  locations                 = var.locations
  app_tag                   = var.app_tag
  aws_instance_type         = var.aws_instance_type
  public_key                = var.public_key
  private_key               = var.private_key
  app_name                  = var.app_name
  bacalhau_installation_id  = var.bacalhau_installation_id
  bacalhau_data_dir         = var.bacalhau_data_dir
  bacalhau_node_dir         = var.bacalhau_node_dir
  bacalhau_config_file_path = var.bacalhau_config_file_path
  username                  = var.username
  providers = {
    aws = aws.primary
  }
}

output "instance_public_ips" {
  value = {
    for region, module in module.regions :
    region => module.public_ips
  }
}
