variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_ssh_key_path" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
}


variable "bacalhau_data_dir" {
  description = "Directory for Bacalhau data"
  type        = string
  default     = "/bacalhau_data"
}

variable "bacalhau_node_dir" {
  description = "Directory for Bacalhau node"
  type        = string
  default     = "/bacalhau_node"
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "instances_per_region" {
  type        = number
  description = "Number of compute instances to deploy per region"
  default     = 5
}

variable "resource_group_region" {
  type        = string
  description = "Region for resource group"
}

variable "locations" {
  type = map(object({
    machine_type = string
    node_count   = number
  }))
  description = "Map of locations with their VM configurations"
}

variable "bacalhau_config_file_path" {
  type        = string
  description = "Path to the Bacalhau config file"
}
