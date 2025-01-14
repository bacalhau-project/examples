module "networkModule" {
  source = "../network"

  app_tag = var.app_tag
  region  = var.region
  zone    = var.zone

  cidr_block_range         = "10.${index(data.aws_availability_zones.available.names, var.zone)}.0.0/16"
  subnet1_cidr_block_range = "10.${index(data.aws_availability_zones.available.names, var.zone)}.1.0/24"
  subnet2_cidr_block_range = "10.${index(data.aws_availability_zones.available.names, var.zone)}.2.0/24"

  providers = {
    aws = aws
  }
}

module "securityGroupModule" {
  source = "../securityGroup"

  region  = var.region
  vpc_id  = module.networkModule.vpc_id
  app_tag = var.app_tag

  providers = {
    aws = aws
  }
}

module "instanceModule" {
  source = "../instance"

  aws_instance_type         = var.aws_instance_type
  instance_ami              = var.instance_ami
  region                    = var.region
  zone                      = var.zone
  node_count                = var.node_count
  vpc_id                    = module.networkModule.vpc_id
  subnet_public_id          = module.networkModule.public_subnets[0]
  security_group_ids        = [module.securityGroupModule.sg_22, module.securityGroupModule.sg_4222]
  app_tag                   = var.app_tag
  public_key_path           = var.public_key_path
  private_key_path          = var.private_key_path
  bacalhau_data_dir         = var.bacalhau_data_dir
  bacalhau_node_dir         = var.bacalhau_node_dir
  bacalhau_config_file_path = var.bacalhau_config_file_path
  username                  = var.username

  providers = {
    aws = aws
  }
}

# Get list of availability zones for CIDR block calculation
data "aws_availability_zones" "available" {
  state = "available"
}

