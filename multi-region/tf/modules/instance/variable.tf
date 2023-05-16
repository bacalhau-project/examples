# Variables

variable "vpc_id" {
  description = "VPC id"
  type        = string
}
variable "subnet_public_id" {
  description = "VPC public subnet id"
  type        = string
}
variable "security_group_ids" {
  description = "EC2 ssh security group"
  type        = list(string)
  default     = []
}
variable "app_tag" {
  description = "Environment tag"
  type        = string
}
variable "key_pair_name" {
  description = "EC2 Key pair name"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "instance_ami" { type = string }

variable "availability_zone" { type = string }
