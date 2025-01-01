locals {
  env_data = jsondecode(file("${path.module}/.env.json"))
}

provider "aws" {
  region = "us-east-1" # Default region, will be overridden in each module
}

module "regions" {
  for_each = local.env_data.locations

  source = "./modules/region"

  region       = each.key
  locations    = local.env_data.locations
  app_tag      = local.env_data.app_tag
  instance_type = local.env_data.aws_instance_type
  public_key   = local.env_data.public_key

  providers = {
    aws = aws
  }
}

output "instance_public_ips" {
  value = {
    for region, module in module.regions :
    region => module.public_ips
  }
}
