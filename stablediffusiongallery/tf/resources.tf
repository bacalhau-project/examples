provider "aws" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

module "networkModule" {
  source            = "./modules/network"
  access_key        = var.access_key
  secret_key        = var.secret_key
  region            = var.region
  app_tag           = var.app_tag
  availability_zone = var.availability_zone
  public_key_path   = var.public_key_path
}

module "securityGroupModule" {
  source     = "./modules/securityGroup"
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
  vpc_id     = module.networkModule.vpc_id
  app_tag    = var.app_tag
}

module "instanceModule" {
  source             = "./modules/instance"
  access_key         = var.access_key
  secret_key         = var.secret_key
  region             = var.region
  instance_type      = var.instance_type
  instance_ami       = var.instance_ami
  vpc_id             = module.networkModule.vpc_id
  subnet_public_id   = module.networkModule.public_subnets[0]
  key_pair_name      = module.networkModule.ec2keyName
  security_group_ids = ["${module.securityGroupModule.sg_22}", "${module.securityGroupModule.sg_80}"]
  app_tag            = var.app_tag
}

module "dnsModule" {
  source      = "./modules/dns"
  access_key  = var.access_key
  secret_key  = var.secret_key
  region      = var.region
  domain_name = "pintura.cloud"
  aRecords = [
    "pintura.cloud ${module.instanceModule.instance_eip}",
  ]
  cnameRecords = [
    "www.pintura.cloud pintura.cloud"
  ]
  app_tag    = var.app_tag
}
