variable "compartment_id" {
  type        = string
  description = "Oracle compartment OCID"
}

variable "region" {
  type        = string
  description = "Oracle region"
}

variable "app_tag" {
  type        = string
  description = "Application tag"
}

variable "instance_shape" {
  type        = string
  description = "Instance shape"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID"
}

variable "nsg_ids" {
  type        = list(string)
  description = "Network security group IDs"
}

variable "ssh_user" {
  type        = string
  description = "SSH username"
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
