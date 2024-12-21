# AWS Instance Module Variables

variable "vpc_id" {
  description = "VPC id"
  type        = string
}

variable "subnet_public_id" {
  description = "VPC public subnet id"
  type        = string
}

variable "security_group_ids" {
  description = "EC2 security groups"
  type        = list(string)
  default     = []
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "username" {
  description = "Username for login"
  type        = string
}

variable "public_key" {
  description = "Public key file that should appear in authorized_keys"
  type        = string
}

variable "aws_instance_type" {
  description = "AWS instance type for compute instances"
  type        = string
}

variable "aws_ami" {
  type        = string
  description = "AMI ID for AWS instances"
}

variable "zone" {
  type        = string
  description = "AWS availability zone"
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "orchestrator_config_path" {
  type        = string
  description = "Path to the Bacalhau orchestrator configuration YAML file"
}

variable "logs_dir" {
  type        = string
  description = "Directory where logs will be generated"
  default     = "/var/log/app"
}

variable "logs_to_process_dir" {
  type        = string
  description = "Directory where logs will be processed"
  default     = "/var/log/logs_to_process"
}
