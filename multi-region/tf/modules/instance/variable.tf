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

variable "pem_file_content" {
  description = "EC2 Key pair private key"
  type        = string
}

variable "shelluser" {
  description = "User to connect to the instance"
  type        = string
}

variable "public_key" {
  description = "OpenSSH public key"
  type        = string
}

variable "private_key" {
  description = "OpenSSH private key"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "instance_ami" { type = string }

variable "zone" { type = string }

variable "region" {
  description = "AWS region"
  type        = string
}

variable "bacalhau_run_file" {
  description = "Bacalhau run file"
  type        = string
}

variable "bootstrap_region" {
  description = "Bootstrap region"
  type        = string
}

variable "tailscale_key" {
  description = "Tailscale key"
  type        = string
}
