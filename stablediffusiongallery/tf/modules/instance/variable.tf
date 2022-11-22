# Variables

variable "access_key" {}
variable "secret_key" {}
variable "region" {}
variable "vpc_id" { description = "VPC id" }
variable "subnet_public_id" { description = "VPC public subnet id" }
variable "security_group_ids" {
  description = "EC2 ssh security group"
  type        = list(string)
  default     = []
}
variable "app_tag" {
  description = "Environment tag"
}
variable "key_pair_name" {
  description = "EC2 Key pair name"
}
variable "instance_ami" { description = "EC2 instance ami" }
variable "instance_type" { description = "EC2 instance type" }
