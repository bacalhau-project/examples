# Variables

variable "node_count" {
  description = "Number of nodes to create"
  type        = number
}

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

variable "public_key_path" {
  description = "Path to the OpenSSH public key"
  type        = string
}

variable "private_key_path" {
  description = "OpenSSH private key"
  type        = string
}

variable "aws_instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "instance_ami" {
  description = "EC2 instance AMI"
  type        = string
}

variable "zone" {
  description = "AWS zone"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "bacalhau_data_dir" {
  description = "Bacalhau data directory"
  type        = string
}

variable "bacalhau_node_dir" {
  description = "Bacalhau node directory"
  type        = string
}

variable "bacalhau_config_file_path" {
  description = "Path to the Bacalhau configuration file"
  type        = string
}

variable "username" {
  description = "Username"
  type        = string
}
