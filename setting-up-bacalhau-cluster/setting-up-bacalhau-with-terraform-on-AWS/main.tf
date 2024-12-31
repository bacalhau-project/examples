
# Provider configurations
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

# Create VPC and base infrastructure for each region
module "region_us_east_1" {
  source = "./modules/region"

  aws = aws.us_east_1

  app_name                 = var.app_name
  app_tag                  = var.app_tag
  bacalhau_installation_id = var.bacalhau_installation_id
  username                 = var.username
  public_key               = var.public_key
  private_key              = var.private_key
  bacalhau_data_dir        = var.bacalhau_data_dir
  bacalhau_node_dir        = var.bacalhau_node_dir
  aws_instance_type        = var.aws_instance_type
  region_config            = var.locations["us-east-1"]
}

module "region_eu_west_1" {
  source = "./modules/region"

  aws = aws.eu_west_1

  app_name                 = var.app_name
  app_tag                  = var.app_tag
  bacalhau_installation_id = var.bacalhau_installation_id
  username                 = var.username
  public_key               = var.public_key
  private_key              = var.private_key
  bacalhau_data_dir        = var.bacalhau_data_dir
  bacalhau_node_dir        = var.bacalhau_node_dir
  aws_instance_type        = var.aws_instance_type
  region_config            = var.locations["eu-west-1"]
}

# Outputs
output "instance_public_ips" {
  value = merge(
    module.region_us_east_1.instance_public_ips,
    module.region_eu_west_1.instance_public_ips
  )
}

output "instance_ids" {
  value = merge(
    module.region_us_east_1.instance_ids,
    module.region_eu_west_1.instance_ids
  )
}
