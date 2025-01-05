# Application Configuration
variable "app_name" {
  type        = string
  description = "Name of the application"
}

variable "app_tag" {
  type        = string
  description = "Environment tag for the application"
}

variable "bacalhau_installation_id" {
  type        = string
  description = "Unique identifier for this Bacalhau installation"
}

# Bacalhau Configuration
variable "bacalhau_data_dir" {
  type        = string
  description = "Directory for Bacalhau data"
}

variable "bacalhau_node_dir" {
  type        = string
  description = "Directory for Bacalhau node configuration"
}

variable "bacalhau_config_file_path" {
  type        = string
  description = "Path to the Bacalhau configuration file"
}

# Access Configuration
variable "username" {
  type        = string
  description = "Username for SSH access to instances"
}

variable "public_key" {
  type        = string
  description = "Path to the public key file for SSH access"
}

variable "private_key" {
  type        = string
  description = "Path to the private key file for SSH access"
}

# AWS Configuration
variable "aws_instance_type" {
  type        = string
  description = "AWS instance type to use"
  default     = "t2.micro"
}

variable "node_count" {
  description = "Number of nodes to create"
  type        = number
}

variable "instance_ami" {
  description = "AMI to use for instances"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "zone" {
  description = "AWS zone"
  type        = string
}
