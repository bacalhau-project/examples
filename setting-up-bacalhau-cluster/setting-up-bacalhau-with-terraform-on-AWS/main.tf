locals {
  env_data = jsondecode(file("${path.module}/.env.json"))
}

provider "aws" {
  alias  = "region"
  region = "us-east-1" # Default region, will be overridden in each module
}

provider "aws" {
  alias  = "default"
  region = "us-east-1"
}

module "regions" {
  for_each = local.env_data.locations

  source = "./modules/region"

  region                   = each.key
  locations                = local.env_data.locations
  app_tag                  = local.env_data.app_tag
  aws_instance_type        = local.env_data.aws_instance_type
  public_key               = local.env_data.public_key
  private_key              = local.env_data.private_key
  app_name                 = local.env_data.app_name
  bacalhau_installation_id = local.env_data.bacalhau_installation_id
  bacalhau_data_dir        = local.env_data.bacalhau_data_dir
  bacalhau_node_dir        = local.env_data.bacalhau_node_dir
  username                 = local.env_data.username

  providers = {
    aws = aws.region
  }
}

output "instance_public_ips" {
  value = {
    for region, module in module.regions :
    region => module.public_ips
  }
}
