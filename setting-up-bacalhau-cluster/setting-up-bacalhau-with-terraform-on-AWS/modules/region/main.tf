provider "aws" {
  region = var.region
}

module "networkModule" {
  source  = "./modules/network"
  app_tag = var.app_tag
  region  = var.region
  zone    = var.locations[var.region].zone

  cidr_block_range         = "10.0.0.0/16"
  subnet1_cidr_block_range = "10.0.1.0/24"
  subnet2_cidr_block_range = "10.0.2.0/24"
}

module "securityGroupModule" {
  source = "./modules/securityGroup"

  vpc_id  = module.networkModule.vpc_id
  app_tag = var.app_tag
}

module "instanceModule" {
  count = var.locations[var.region].node_count

  source = "./modules/instance"

  instance_type      = var.instance_type
  instance_ami       = var.locations[var.region].instance_ami
  region             = var.region
  zone               = var.locations[var.region].zone
  vpc_id             = module.networkModule.vpc_id
  subnet_public_id   = module.networkModule.public_subnets[0]
  security_group_ids = [module.securityGroupModule.sg_22, module.securityGroupModule.sg_4222]
  app_tag            = "${var.app_tag}-${count.index}"
  public_key         = var.public_key
}

output "public_ips" {
  value = module.instanceModule[*].public_ip
}

