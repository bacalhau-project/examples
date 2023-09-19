terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "tls_private_key" "tls_pk" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "keypair" {
  key_name   = "${var.app_tag}-key-pair-${var.region}"
  public_key = tls_private_key.tls_pk.public_key_openssh
}

resource "local_sensitive_file" "pem_file" {
  filename             = pathexpand("./${var.app_tag}-key-pair-${var.region}.pem")
  file_permission      = "600"
  directory_permission = "700"
  content              = tls_private_key.tls_pk.private_key_pem
}
module "networkModule" {
  source  = "./modules/network"
  app_tag = var.app_tag
  region  = var.region
  zone    = var.locations[var.region].availability_zone

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
  source = "./modules/instance"

  instance_type      = var.instance_type
  instance_ami       = var.locations[var.region].instance_ami
  region             = var.region
  zone               = var.locations[var.region].availability_zone
  vpc_id             = module.networkModule.vpc_id
  subnet_public_id   = module.networkModule.public_subnets[0]
  security_group_ids = [module.securityGroupModule.sg_22, module.securityGroupModule.sg_1234, module.securityGroupModule.sg_1235]
  app_tag            = var.app_tag
  bacalhau_run_file  = var.bacalhau_run_file
  bootstrap_region   = var.bootstrap_region

  key_pair_name    = aws_key_pair.keypair.key_name
  pem_file_content = local_sensitive_file.pem_file.content
  shelluser        = var.shelluser
  public_key       = var.public_key
  private_key      = var.private_key
  tailscale_key    = var.tailscale_key
}

