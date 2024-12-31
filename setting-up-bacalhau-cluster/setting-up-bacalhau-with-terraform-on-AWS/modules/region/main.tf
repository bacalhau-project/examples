
variable "aws" {
  type = any
}

provider "aws" {
  alias = "region"
}

# Input variables
variable "app_name" {}
variable "app_tag" {}
variable "bacalhau_installation_id" {}
variable "username" {}
variable "public_key" {}
variable "private_key" {}
variable "bacalhau_data_dir" {}
variable "bacalhau_node_dir" {}
variable "aws_instance_type" {}
variable "region_config" {}

# Outputs
output "instance_public_ips" {
  value = {}
}

output "instance_ids" {
  value = {}
}
