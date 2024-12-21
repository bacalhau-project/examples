# Common Variables
variable "app_name" {
  type        = string
  description = "Application name to propagate to resources"
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

# GCP-specific Variables
variable "gcp_project_id" {
  description = "The GCP project ID to deploy to"
}

variable "gcp_regions" {
  type        = list(string)
  description = "List of GCP regions to deploy resources"
}

variable "gcp_machine_type" {
  type        = string
  description = "GCP machine type for compute instances"
  default     = "n1-standard-2"
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

# Azure-specific Variables
variable "azure_subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "azure_regions" {
  type        = list(string)
  description = "List of Azure regions to deploy resources"
}

variable "azure_vm_size" {
  type        = string
  description = "Azure VM size for compute instances"
  default     = "Standard_D2s_v3"
}

# Oracle Cloud-specific Variables
variable "oci_tenancy_ocid" {
  type        = string
  description = "Oracle Cloud Infrastructure tenancy OCID"
}

variable "oci_regions" {
  type        = list(string)
  description = "List of Oracle Cloud regions to deploy resources"
}

variable "oci_instance_shape" {
  type        = string
  description = "Oracle Cloud compute instance shape"
  default     = "VM.Standard2.2"
}

# Resource Count Variables
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

# Central Logging Configuration
variable "central_logging_bucket" {
  type        = string
  description = "Name of the central GCP bucket for aggregated logging"
}

variable "central_logging_region" {
  type        = string
  description = "GCP region for central logging bucket"
  default     = "us-central1"
}

variable "create_node_info" {
  description = "Base64 encoded create_node_info.sh script"
  type        = string
}
