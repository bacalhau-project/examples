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

variable "username" {
  description = "User to connect to the instance"
  type        = string
}

variable "public_key" {
  description = "OpenSSH public key"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "instance_ami" {
  type        = string
  description = "AMI ID for the instance"
}

variable "zone" {
  type        = string
  description = "Availability zone"
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "orchestrator_config_path" {
  type        = string
  description = "Path to the Bacalhau orchestrator configuration YAML file"
}
