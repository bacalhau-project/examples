# Common Variables
variable "app_name" {
  type        = string
  description = "application name to propagate to resources"
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_key" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
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

variable "bacalhau_installation_id" {
  type        = string
  description = "Bacalhau installation ID for tracking compute nodes"
}

# AWS-specific Variables
variable "aws_regions" {
  type        = list(string)
  description = "List of AWS regions to deploy resources"
}

variable "aws_instance_type" {
  type        = string
  description = "AWS instance type for compute instances"
  default     = "t2.medium"
}

variable "instances_per_region" {
  type        = number
  description = "Number of compute instances to deploy per region"
  default     = 5
}

variable "buckets_per_region" {
  type        = number
  description = "Number of storage buckets to deploy per region"
  default     = 5
}

variable "central_logging_bucket" {
  type        = string
  description = "Name of the central GCP bucket for aggregated logging"
}

# AWS Network Configuration
variable "aws_ami" {
  type        = string
  description = "AMI ID for AWS instances"
  default     = "ami-0c7217cdde317cfec"
}

variable "aws_vpc_cidr" {
  type        = string
  description = "CIDR block for VPC"
  default     = "10.0.0.0/16"
}

variable "aws_subnet_cidr" {
  type        = string
  description = "CIDR block for subnet"
  default     = "10.0.1.0/24"
}
