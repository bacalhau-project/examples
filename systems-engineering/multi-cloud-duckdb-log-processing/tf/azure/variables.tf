variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "region" {
  description = "Azure region"
  type        = string
}

variable "locations" {
  description = "Locations and resources to deploy"
  type        = map(map(string))
}

variable "vm_size" {
  description = "Azure VM size"
  type        = string
}

variable "bootstrap_region" {
  description = "Region where the bootstrap node will be created"
  type        = string
}

variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau Run File location"
}

variable "admin_username" {
  type        = string
  description = "Admin username for VMs"
}

variable "public_key" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
}

variable "private_key" {
  type        = string
  description = "Private key file used to connect to the instance"
}

variable "tailscale_key" {
  description = "Tailscale key"
  type        = string
}
