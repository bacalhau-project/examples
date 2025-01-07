variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "app_tag" {
  type        = string
  description = "Application tag"
}

variable "vm_size" {
  type        = string
  description = "VM size"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID"
}

variable "nsg_id" {
  type        = string
  description = "Network security group ID"
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_key_path" {
  type        = string
  description = "Public key file path"
}

variable "node_count" {
  description = "Number of VMs to create"
  type        = number
  default     = 1
}

variable "bacalhau_config_file" {
  description = "Bacalhau config file"
  type        = string
}
