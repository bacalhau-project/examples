terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

module "networkModule" {
  source          = "./modules/network"
  app_tag         = var.app_tag
  public_key_path = var.public_key_path

  cidr_block_range         = "10.${var.index * 10}.0.0/16"
  subnet1_cidr_block_range = "10.${var.index * 10}.1.0/24"
  subnet2_cidr_block_range = "10.${var.index * 10}.2.0/24"
}

module "securityGroupModule" {
  source = "./modules/securityGroup"

  vpc_id  = module.networkModule.vpc_id
  app_tag = var.app_tag
}

# module "tgw" {
#   source  = "terraform-aws-modules/transit-gateway/aws"
#   version = "~> 2.0"

#   name        = "my-tgw"
#   description = "My TGW shared with several other AWS accounts"

#   enable_auto_accept_shared_attachments = true

#   vpc_attachments = {
#     vpc = {
#       vpc_id       = module.networkModule.vpc_id
#       subnet_ids   = module.network.vpc_public_subnets
#       dns_support  = true
#       ipv6_support = true

#       tgw_routes = [
#         {
#           destination_cidr_block = "30.0.0.0/16"
#         },
#         {
#           blackhole              = true
#           destination_cidr_block = "40.0.0.0/20"
#         }
#       ]
#     }
#   }

#   ram_allow_external_principals = true
#   ram_principals                = [307990089504]

#   tags = {
#     Purpose = "tgw-complete-example"
#   }
# }

module "instanceModule" {
  source = "./modules/instance"

  instance_type      = var.instance_type
  instance_ami       = var.locations[var.index].instance_ami
  availability_zone  = var.locations[var.index].availability_zone
  vpc_id             = module.networkModule.vpc_id
  subnet_public_id   = module.networkModule.public_subnets[0]
  key_pair_name      = module.networkModule.ec2keyName
  security_group_ids = [module.securityGroupModule.sg_22, module.securityGroupModule.sg_80]
  app_tag            = var.app_tag
}
