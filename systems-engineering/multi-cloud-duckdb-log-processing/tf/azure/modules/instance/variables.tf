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

variable "admin_username" {
  type        = string
  description = "Admin username"
}

variable "public_key" {
  type        = string
  description = "Public key file path"
}

variable "private_key" {
  type        = string
  description = "Private key file path"
}

variable "tailscale_key" {
  type        = string
  description = "Tailscale key"
}

variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau run file location"
}

variable "bootstrap_region" {
  type        = string
  description = "Bootstrap region"
}
